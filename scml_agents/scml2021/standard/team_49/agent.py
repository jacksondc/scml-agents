import os
import sys
sys.path.append(os.path.dirname(__file__))
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from negmas import (AgentMechanismInterface, Breach, Contract,
                    MechanismState, Issue, Negotiator)
from scml.scml2020 import SCML2020Agent, PredictionBasedTradingStrategy, SupplyDrivenProductionStrategy
from scml.scml2020.world import Failure, AWI

from negotiation_manager import NegotiationManager

__all__ = [ "E3BIUagent", ]

class E3BIUagent(NegotiationManager, PredictionBasedTradingStrategy, SupplyDrivenProductionStrategy, SCML2020Agent):

    # =====================
    # Time-Driven Callbacks
    # =====================

    def init(self):
        """Called once after the agent-world interface is initialized"""
        super(E3BIUagent, self).init()

    def step(self):
        """Called at every production step by the world"""
        super(E3BIUagent, self).step()

    # ================================
    # Negotiation Control and Feedback
    # ================================

    def on_negotiation_failure(self,
                               partners: List[str],
                               annotation: Dict[str, Any],
                               mechanism: AgentMechanismInterface,
                               state: MechanismState
                               ) -> None:
        """Called when a negotiation the agent is a party of ends without
        agreement"""

    def on_negotiation_success(self,
                               contract: Contract,
                               mechanism: AgentMechanismInterface) -> None:
        """Called when a negotiation the agent is a party of ends with
        agreement"""

    # =============================
    # Contract Control and Feedback
    # =============================

    def on_contract_executed(self, contract: Contract) -> None:
        """Called when a contract executes successfully and fully"""

    def on_contract_breached(self,
                             contract: Contract,
                             breaches: List[Breach],
                             resolution: Optional[Contract]
                             ) -> None:
        """Called when a breach occur. In 2020, there will be no resolution
        (i.e. resoluion is None)"""

    # ====================
    # Production Callbacks
    # ====================

    def confirm_production(self, commands: np.ndarray, balance: int,
                           inventory: np.ndarray) -> np.ndarray:
        """
        Called just before production starts at every step allowing the
        agent to change what is to be produced in its factory on that step.
        """
        return commands

    def on_failures(self, failures: List[Failure]) -> None:
        """Called when production fails. If you are careful in
        what you order in `confirm_production`, you should never see that."""

    def target_quantities(self, steps: Tuple[int, int], sell: bool) -> np.ndarray:
        """Implemented for speed but not really required"""

        if sell:
            needed, secured = self.outputs_needed, self.outputs_secured
        else:
            needed, secured = self.inputs_needed, self.inputs_secured

        return needed[steps[0]: steps[1]] - secured[steps[0]: steps[1]]

    def respond_to_negotiation_request(
            self,
            initiator: str,
            issues: List["Issue"],
            annotation: Dict[str, Any],
            mechanism: "AgentMechanismInterface",
    ) -> Optional["Negotiator"]:

        # Don't make a negotiation in case the agent has breached
        breached_agent_name = annotation["buyer"] if annotation["is_buy"] else annotation["seller"]
        if self.is_breached_last_n_steps(breached_agent_name, 25):
            return None

        if self.is_agent_unique(annotation["is_buy"]) and self.get_agent_type(
                breached_agent_name) != self.type_name:
            return None
        return super().respond_to_negotiation_request(initiator, issues, annotation, mechanism)

    def is_breached_last_n_steps(self, agent_id, nsteps):
        if self.awi.reports_of_agent(agent_id) is not None:
            breach_levels = [step.breach_level for step in self.awi.reports_of_agent(agent_id).values()]
            if sum(breach_levels[-nsteps:]) > 0:
                return True
        return False

    def start_negotiations(
        self,
        product: int,
        quantity: int,
        unit_price: int,
        step: int,
        partners: List[str] = None,
    ) -> None:
        """
        Starts a set of negotiations to buy/sell the product with the given limits

        Args:
            product: product type. If it is an input product, negotiations to buy it will be started otherweise to sell.
            quantity: The maximum quantity to negotiate about
            unit_price: The maximum/minimum unit price for buy/sell
            step: The maximum/minimum time for buy/sell
            partners: A list of partners to negotiate with

        Remarks:

            - This method assumes that product is either my_input_product or my_output_product

        """
        awi: AWI
        awi = self.awi  # type: ignore
        is_seller = product == self.awi.my_output_product
        if quantity < 1 or unit_price < 1 or step < awi.current_step + 1:
            return

        q_val = (1, quantity)
        t_val = self._trange(step, is_seller)
        u_val = self._urange(step, is_seller, t_val)
        if t_val[0] > t_val[1]:
            return
        if partners is None:
            if is_seller:
                partners = self.awi.my_consumers
            else:
                partners = self.awi.my_suppliers

        partners = [partner for partner in partners if not self.is_breached_last_n_steps(partner, 20)]
        if self.is_agent_unique(is_seller):
            partners = [partner for partner in partners if self.get_agent_type(partner) == self.type_name]
        return super()._start_negotiations(
            product, is_seller, step, q_val, u_val, t_val, partners
        )

    def is_agent_unique(self, is_buy):
        if is_buy:
            for consumer_name in self._awi.my_consumers:
                if self.get_agent_type(consumer_name) == self.type_name:
                    return True
        else:
            for supplier_name in self._awi.my_suppliers:
                if self.get_agent_type(supplier_name) == self.type_name:
                    return True
        return False    

    def get_agent_type(self, agent_name):
        if agent_name in ['BUYER', 'SELLER']:
            return agent_name
        return self.awi._world.agent_types[self.awi._world.a2i[agent_name]]