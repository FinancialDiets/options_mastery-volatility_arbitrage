"""Weighted variance swaps"""

# pylint: disable=line-too-long, too-many-arguments,too-many-locals

from abc import ABC, abstractmethod

import numpy as np
import numpy.typing as npt

from volatility_arbitrage.pricing_model.heston_model import Correlation, HestonParams

ARRAY = npt.NDArray[np.float64]


class WeightedVarianceSwap(ABC):
    """
    Base class for weighted variance swap.
    Lee, R. (2010). Weighted variance swap. Encyclopedia of quantitative finance.
    """

    def __init__(
        self,
        imp_var_params: HestonParams,
        real_var_params: HestonParams,
        corr: Correlation,
    ) -> None:
        self.imp_var_params = imp_var_params
        self.real_var_params = real_var_params
        self.corr = corr

    @abstractmethod
    def price(self, *, imp_var: ARRAY, tau: ARRAY) -> ARRAY:
        """
        :param imp_var: instantaneous implied variance
        :param tau: time to expiry in years
        :return: price of weighted variance swap
        """

    @abstractmethod
    def var_vega(self, tau: ARRAY) -> ARRAY:
        """
        :param tau: time to expiry in years
        :return: variance vega
        """

    def forward_var_vega(self, tau_front: ARRAY, tau_back: ARRAY) -> ARRAY:
        """
        :param tau_front: time to expiry in years
        :param tau_back: time to expiry in years
        :return: forward variance vega
        """
        return self.var_vega(tau_back) - self.var_vega(tau_front)

    def var_skew_stikiness_ratio(self, *, real_var: ARRAY, imp_var: ARRAY) -> ARRAY:
        """
        :param real_var: instantaneous realized variance
        :param imp_var: instantanoues implied variance
        :return: SSR with respect to implied instantaneous variance = d imp_var d log(F) / (d log(F))^2
        """
        return (
            self.corr.rho_spot_imp
            * self.imp_var_params.vol_of_var
            * np.sqrt(imp_var)
            / np.sqrt(real_var)
        )

    def min_var_delta(
        self, *, real_var: ARRAY, imp_var: ARRAY, tau_0: ARRAY, tau_t: ARRAY
    ) -> ARRAY:
        """
        :param real_var: instantaneous realized variance
        :param imp_var: instantanoues implied variance
        :param tau_0: time to expiry in years at time 0
        :param tau_t: time to expiry in years at time t
        :return: minimum variance delta
        """
        # forward_var_vega is used because at the next timestamp variance between time 0 and 1 is not a risk.
        forward_var_vega = self.forward_var_vega(tau_front=tau_0 - tau_t, tau_back=tau_0)
        ssr = self.var_skew_stikiness_ratio(real_var=real_var, imp_var=imp_var)
        return forward_var_vega * ssr

    def total_pnl(
        self,
        *,
        f_0: ARRAY,
        f_t: ARRAY,
        real_var_0: ARRAY,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        imp_var_t: ARRAY,
        tau_t: ARRAY,
    ) -> ARRAY:
        """
        :param f_0: forward price at time 0
        :param f_t: forward price at time t
        :param real_var_0: instantaneous realize variacnce at time 0
        :param imp_var_0: instantaneous implied variance at time 0
        :param tau_0: time to expiry in years at time 0
        :param imp_var_t: instantaneous implied variance at time t
        :param tau_t: time to expiry in years at time t
        :return: total P&L
        """
        price_0 = self.price(imp_var=imp_var_0, tau=tau_0)
        price_t = self.price(imp_var=imp_var_t, tau=tau_t)
        vanna_pnl = self.vanna_pnl(
            imp_var_0=imp_var_0, tau_0=tau_0, imp_var_t=imp_var_t, tau_t=tau_t, f_0=f_0, f_t=f_t
        )
        gamma_pnl = self.gamma_pnl(f_0=f_0, f_t=f_t)
        vega_hedge_pnl = self.vega_hedge_pnl(
            f_0=f_0, f_t=f_t, real_var_0=real_var_0, imp_var_0=imp_var_0, tau_0=tau_0, tau_t=tau_t
        )
        return price_t - price_0 + vanna_pnl + gamma_pnl + vega_hedge_pnl

    @staticmethod
    @abstractmethod
    def gamma_pnl(*, f_0: ARRAY, f_t: ARRAY) -> ARRAY:
        """
        :param f_0: forward price at time 0
        :param f_t: fowward price at time t
        :return: Gamma P&L
        """

    def theta_pnl(
        self,
        *,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        tau_t: ARRAY,
    ) -> ARRAY:
        """
        :param imp_var_0: instantaneous implied variance at time 0
        :param tau_0: time to expiry in years at time 0
        :param tau_t: time to expiry in years at time t
        :return: expected Theta P&L at time 0
        """
        return -self.price(imp_var=imp_var_0, tau=tau_t - tau_0)

    def var_vega_pnl(
        self,
        *,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        imp_var_t: ARRAY,
        tau_t: ARRAY,
    ) -> ARRAY:
        """
        :param imp_var_0: instantaneous implied variance at time 0
        :param tau_0: time to expiry in years at time 0
        :param imp_var_t: instantaneous implied variance at time t
        :param exp_imp_var_t: E[imp_var_t|imp_var_0]
        :param tau_t: time to expiry in years at time t
        :return: variance Vega P&L
        """
        price_0 = self.price(imp_var=imp_var_0, tau=tau_0)
        price_t = self.price(imp_var=imp_var_t, tau=tau_t)
        theta_pnl = self.theta_pnl(imp_var_0=imp_var_0, tau_0=tau_0, tau_t=tau_t)
        return price_t - price_0 - theta_pnl

    @abstractmethod
    def vanna_pnl(
        self,
        *,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        imp_var_t: ARRAY,
        tau_t: ARRAY,
        f_0: ARRAY,
        f_t: ARRAY,
    ) -> ARRAY:
        """
        :param imp_var_0: instantaneous implied variance at time 0
        :param tau_0: time to expiry in years at time 0
        :param imp_var_t: instantaneous implied variance at time t
        :param tau_t: time to expiry in years at time t
        :param f_0: forward price at time 0
        :param f_t: forward price at time t
        :return: Vanna P&L
        """

    def vega_hedge_pnl(
        self,
        *,
        f_0: ARRAY,
        f_t: ARRAY,
        real_var_0: ARRAY,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        tau_t: ARRAY,
    ) -> ARRAY:
        """
        :param f_0: forward price at time 0
        :param f_t: forward price at time t
        :param real_var_0: instantaneous realized variance at time 0
        :param imp_var_0: instantaneous implied variance at time 0
        :param tau_0: time to expiry in years at time 0
        :param tau_t: time to expiry in years at time t
        :return: Vega hedge P&L
        """
        min_var_delta = self.min_var_delta(
            real_var=real_var_0, imp_var=imp_var_0, tau_0=tau_0, tau_t=tau_t
        )
        return -min_var_delta * (f_t - f_0)


class VarianceSwap(WeightedVarianceSwap):
    """
    Standard variance swap or log contract.
    Neuberger, A. (1994). The log contract. Journal of portfolio management, 20(2), 74.
    Fukasawa, M. (2014). Volatility derivatives and model-free implied leverage. International Journal of Theoretical and Applied Finance, 17(01), 1450002.
    """

    def price(self, *, imp_var: ARRAY, tau: ARRAY) -> ARRAY:
        return (
            self.imp_var_params.mean_of_var * tau
            + (imp_var - self.imp_var_params.mean_of_var)
            * (1 - np.exp(-self.imp_var_params.kappa * tau))
            / self.imp_var_params.kappa
        )

    def var_vega(self, tau: ARRAY) -> ARRAY:
        return (1 - np.exp(-self.imp_var_params.kappa * tau)) / self.imp_var_params.kappa

    def vanna_pnl(
        self,
        *,
        imp_var_0: ARRAY,
        tau_0: ARRAY,
        imp_var_t: ARRAY,
        tau_t: ARRAY,
        f_0: ARRAY,
        f_t: ARRAY,
    ) -> ARRAY:
        return np.zeros_like(imp_var_0)

    @staticmethod
    def gamma_pnl(*, f_0: ARRAY, f_t: ARRAY) -> ARRAY:
        return 2 * (f_t / f_0 - 1 - np.log(f_t / f_0))
