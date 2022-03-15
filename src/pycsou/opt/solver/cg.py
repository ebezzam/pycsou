import typing as typ

import numpy as np

import pycsou.abc.operator as pyco
import pycsou.abc.solver as pycs
import pycsou.opt.stop as pycos
import pycsou.runtime as pycrt
import pycsou.util as pycu
import pycsou.util.ptype as pyct


class CG(pycs.Solver):
    r"""
     Conjugate Gradient Method.

     The Conjugate Gradient method solves the minimization problem

     .. math::

        \min_{x\in\mathbb{R}^{N}} \frac{1}{2} \mathbf{x}^{T} \mathbf{A} \mathbf{x} - \mathbf{x}^{T} \mathbf{b},

     where :math:`\mathbf{A}: \mathbb{R}^{N} \to \mathbb{R}^{N}` is a *symmetric* *positive definite*
     operator, and :math:`\mathbf{b} \in \mathbb{R}^{N}`.

     The norm of the `explicit residual <https://www.wikiwand.com/en/Conjugate_gradient_method>`_
     :math:`\mathbf {r}_{k+1}:=\mathbf{b}-\mathbf{Ax}_{k+1}}` is used as the default stopping criteria. This provides a
     guaranteed level of accuracy both in exact arithmetic and in the presence of the rounding errors. By default, the
     iterations stop when the norm of the explicit residual is smaller than 1e-4.


     ``CG.fit()`` **Parameterization**

     b: NDArray
         (..., N) 'b' terms in the CG cost function. All problems are solved in parallel.
     x0: NDArray
        (..., N) initial point(s). Defaults to 0 if unspecified.

    **Remark:** 'x0' can be any array with the same shape as 'b' or with any other shape that is broadcastable with the
    shape of 'b'. In the latter case, the initial point(s) are broadcasted following the `numpy broadcasting rules
    <https://numpy.org/doc/stable/user/basics.broadcasting.html.>`_.

     Examples
     --------
     To construct a concrete map, it is recommended to subclass :py:class:`~pycsou.abc.operator.Map` as ilustrated
     in the following example:

     >>> import numpy as np
     >>> from pycsou.abc import LinOp
     >>> rng = np.random.default_rng(seed=0)
     >>> mat = rng.normal(size=(10, 10))
     >>> x_star = rng.normal(size=(2, 2, 10))
     >>> # Create a PSD linear operator
     >>> linop = LinOp.from_array(mat).gram()
     >>> b = linop.apply(x_star)
     >>> cg = CG(linop, show_progress=False)
     >>> cg.fit(b=b)
     >>> assert np.allclose(x_star, cg.solution())

     .. Warning::

         This  is a simplified example for illustration puposes only. It may not abide by all the rules listed in the
         :ref:`developer-notes`.

    """

    def __init__(
        self,
        A: pyco.PosDefOp,
        *,
        folder: typ.Optional[pyct.PathLike] = None,
        exist_ok: bool = False,
        writeback_rate: typ.Optional[int] = None,
        verbosity: int = 1,
        show_progress: bool = True,
        log_var: pyct.VarName = ("x",),
    ):
        super().__init__(
            folder=folder,
            exist_ok=exist_ok,
            writeback_rate=writeback_rate,
            verbosity=verbosity,
            show_progress=show_progress,
            log_var=log_var,
        )

        self._A = A

    @pycrt.enforce_precision(i=["b", "x0"], allow_None=True)
    def m_init(
        self,
        b: pyct.NDArray,
        x0: typ.Optional[pyct.NDArray] = None,
    ):
        mst = self._mstate  # shorthand

        mst["b"] = b
        xp = pycu.get_array_module(b)
        if x0 is None:
            mst["x"] = xp.zeros_like(b)
        else:
            mst["x"] = x0

        # 2-stage res-computation guarantees RT-precision in case apply() not
        # enforce_precision()-ed.
        mst["residual"] = xp.zeros_like(b)
        mst["residual"][:] = b - self._A.apply(mst["x"])
        mst["conjugate_dir"] = mst["residual"].copy()

    def m_step(self):
        mst = self._mstate  # shorthand
        x, r, p = mst["x"], mst["residual"], mst["conjugate_dir"]
        xp = pycu.get_array_module(x)

        Ap = self._A.apply(p)
        rr = xp.linalg.norm(r, ord=2, axis=-1, keepdims=True) ** 2
        alpha = rr / (p * Ap).sum(axis=-1, keepdims=True)
        x += alpha * p
        r -= alpha * Ap
        beta = xp.linalg.norm(r, ord=2, axis=-1, keepdims=True) ** 2 / rr
        p *= beta
        p += r

        # for homogenity with other solver code. Optional in CG due to in-place computations.
        mst["x"], mst["residual"], mst["conjugate_dir"] = x, r, p

    def default_stop_crit(self) -> pycs.StoppingCriterion:
        def explicit_residual(x):
            mst = self._mstate  # shorthand
            residual = mst["b"].copy()
            residual -= self._A.apply(x)
            return residual

        stop_crit = pycos.AbsError(
            eps=1e-4,
            var="x",
            f=explicit_residual,
            norm=2,
            satisfy_all=True,
        )
        return stop_crit

    def solution(self) -> pyct.NDArray:
        """
        Returns
        -------
        p: NDArray
            (..., N) solution.
        """
        data, _ = self.stats()
        return data.get("x")
