from __future__ import annotations

from typing import Any, Protocol


class PrimitiveAction(Protocol):
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool: ...


class EmitEpisodeAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        text = (params or {}).get("text", "")
        if text:
            believes.task_log.append(text[:200])
        return True


class UpdateBeliefAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        key = p.get("key", "")
        value = p.get("value", p.get("new_value", True))
        if key:
            try:
                setattr(believes, key, value)
            except (ValueError, AttributeError):
                pass
            try:
                setattr(believes, f"_{key}_set", True)
            except (ValueError, AttributeError):
                pass
            if key == "new_day":
                believes.new_day = bool(str(value).lower() == "true" if isinstance(value, str) else value)
        return True


class ConsumeResourceAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        key = p.get("key", "")
        amount = int(float(str(p.get("amount", 0))))
        if key == "time_left_on_day":
            personality = getattr(believes, 'personality', 0.3)
            efficiency = 1.0 - (personality - 0.3) * 0.4
            amount = max(1, int(amount * efficiency))
            believes.time_left_on_day = max(0, believes.time_left_on_day - amount)
        elif key == "money":
            believes.money = max(0, believes.money - amount)
        elif key == "seeds":
            believes.seeds = max(0, believes.seeds - amount)
        elif key == "water_available":
            believes.water_available = max(0, believes.water_available - amount)
        elif key == "tools":
            believes.tools = max(0, believes.tools - amount)
        return True


class SendEventAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        send_guard = p.get("_send_guard_event")
        agent = p.get("_agent_alias", "")
        to = p.get("to", "")
        msg_type = p.get("type", "")
        payload = p.get("payload", {})
        if send_guard and to and msg_type:
            send_guard(to, msg_type, payload | {"from": agent})
        return True


class SendMarketPlaceEventAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        send_guard = p.get("_send_guard_event")
        agent = p.get("_agent_alias", "")
        mtype = p.get("message_type", "")
        quantity = int(float(str(p.get("quantity", "1"))))
        reset = str(p.get("reset_resource_needed", "true")).lower() == "true"
        if send_guard and mtype:
            from ethosterra.agents.market_place import MarketPlaceMessage, MarketPlaceMessageType
            mapped = {
                "ASK_FOR_PRICE_LIST": MarketPlaceMessageType.GET_PRICES,
                "BUY_SEEDS": MarketPlaceMessageType.BUY_RESOURCES,
                "BUY_WATER": MarketPlaceMessageType.BUY_RESOURCES,
                "BUY_PESTICIDES": MarketPlaceMessageType.BUY_RESOURCES,
                "BUY_TOOLS": MarketPlaceMessageType.BUY_RESOURCES,
                "BUY_SUPPLIES": MarketPlaceMessageType.BUY_RESOURCES,
                "BUY_LIVESTOCK": MarketPlaceMessageType.BUY_RESOURCES,
            }
            resource_map = {
                "BUY_SEEDS": "seeds", "BUY_WATER": "water",
                "BUY_PESTICIDES": "pesticides", "BUY_TOOLS": "tools",
                "BUY_SUPPLIES": "supplies", "BUY_LIVESTOCK": "livestock",
            }
            msg = MarketPlaceMessage(
                message_type=mapped.get(mtype, MarketPlaceMessageType.GET_PRICES),
                peasant_alias=agent,
                resource=resource_map.get(mtype, mtype.lower()),
                quantity=quantity,
            )
            send_guard("MarketPlace", mtype, msg)
            if reset and mtype in resource_map:
                setattr(believes, f"needs_{resource_map[mtype]}", False)
        return True


class SendCivicAuthorityLandRequestAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        send_guard = p.get("_send_guard_event")
        agent = p.get("_agent_alias", "")
        if send_guard:
            from ethosterra.agents.civic_authority import CivicAuthorityMessage
            believes.farm_name = True
            msg = CivicAuthorityMessage("REQUEST_LAND", peasant_alias=agent)
            send_guard("CivicAuthority", "REQUEST_LAND", msg)
        return True


class EmitEmotionAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        axis = p.get("axis", "happiness")
        delta = float(p.get("delta", 0))
        try:
            current = getattr(believes, axis, believes.happiness)
        except AttributeError:
            current = 0.0
        try:
            setattr(believes, axis, max(-1.0, min(1.0, current + delta)))
        except (ValueError, AttributeError):
            pass
        return True


class IncreaseHealthAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        import random
        p = params or {}
        factor = 1.0
        if getattr(believes, 'emotions_enabled', False):
            factor = 0.5 + getattr(believes, 'happiness', 0.0)
        heal = random.random() * 0.21 * factor
        believes.health = min(1.0, believes.health + heal)
        return True


class SyncClockAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        return True


class LogAuditAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        return True


class IncrementBeliefAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        key = p.get("key", "")
        amount = float(p.get("amount", 1))
        if key:
            try:
                v = getattr(believes, key, 0)
            except AttributeError:
                v = 0
            if isinstance(v, (int, float)):
                new_val = v + amount
                if key == "money":
                    new_val = max(0.0, new_val)
                try:
                    setattr(believes, key, new_val)
                except (ValueError, AttributeError):
                    pass
                try:
                    setattr(believes, f'_{key}_incremented', True)
                except (ValueError, AttributeError):
                    pass
        return True


class WaitForEventAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        return True


class ConditionalAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        key = p.get("key", "money")
        threshold = int(p.get("threshold", 0))
        val = getattr(believes, key, 0)
        if val >= threshold:
            for action in p.get("then", []):
                a = ACTIONS.get(action.get("action"))
                if a:
                    a.execute(believes, action.get("args", {}))
        return True


class SendSocietyCollaborationAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        send_guard = p.get("_send_guard_event")
        agent = p.get("_agent_alias", "")
        flag = p.get("flag", "")
        days = int(p.get("amount", 5))
        if send_guard and flag:
            from ethosterra.agents.community_dynamics import CommunityDynamicsMessage
            action_type = "OFFER_HELP" if "offer" in str(p.get("guard", "")).lower() else "REQUEST_WORKER"
            msg = CommunityDynamicsMessage(action_type, worker_alias=agent, days=days)
            send_guard("CommunityDynamics", action_type, msg)
            setattr(believes, flag, True)
        return True


class SpendFriendsTimeAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        delta = float(p.get("happiness_gain", 0.05))
        believes.happiness = min(1.0, believes.happiness + delta)
        believes.social_capital = min(1.0, believes.social_capital + 0.02)
        return True


class AgroEcosystemAction:
    _STAGE_AFTER = {
        "PREPARE": "PLANTING",
        "PLANT": "GROWING",
        "CHECK": None,
        "IRRIGATE": "IRRIGATED",
        "PESTICIDE": "TREATED",
        "HARVEST": "FALLOW",
        "DEFOREST": "NONE",
        "SELL": None,
    }

    _CROP_PRICES = {
        "water": 3, "seeds": 50000, "pesticides": 9300,
        "tools": 50000, "livestock": 2400, "supplies": 40000,
        "rice": 1100, "roots": 1000, "maiz": 1100,
        "frijol": 1100, "cafe": 1100, "platano": 1100,
    }

    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        send_guard = p.get("_send_guard_event")
        agent = p.get("_agent_alias", "")
        op = p.get("operation", "")

        if op == "SELL":
            hw = getattr(believes, 'harvested_weight', 0)
            if hw > 0:
                crop = getattr(believes, 'last_crop_type', 'maiz') or 'maiz'
                price_per_unit = self._CROP_PRICES.get(crop, 700)
                revenue = hw * price_per_unit
                believes.money += revenue
                believes.harvested_weight = 0
                believes.food_security = min(1.0, getattr(believes, 'food_security', 0) + 0.3)
                believes.task_log.append(f"Vendí {hw:.0f} de {crop} por ${revenue:.0f}")
            return True

        if send_guard and op:
            from ethosterra.agents.agro_ecosystem import AgroEcosystemMessage, AgroEcosystemMessageType
            op_map = {
                "CHECK": AgroEcosystemMessageType.CROP_INFORMATION,
                "DEFOREST": AgroEcosystemMessageType.CROP_INIT,
                "HARVEST": AgroEcosystemMessageType.CROP_HARVEST,
                "IRRIGATE": AgroEcosystemMessageType.CROP_IRRIGATION,
                "PESTICIDE": AgroEcosystemMessageType.CROP_PESTICIDE,
                "PLANT": AgroEcosystemMessageType.CROP_INIT,
                "PREPARE": AgroEcosystemMessageType.CROP_INIT,
                "SELL": AgroEcosystemMessageType.CROP_INFORMATION,
            }
            crop_type = p.get("crop_type", "")
            if not crop_type and hasattr(believes, 'lands') and believes.lands:
                crop_type = believes.lands[0].crop_type or ""
            new_stage = self._STAGE_AFTER.get(op)
            target_land = None
            if believes.lands:
                if new_stage:
                    if op == "PREPARE":
                        target_land = next((l for l in believes.lands if l.stage in ("NONE", "FALLOW")), None)
                    elif op == "PLANT":
                        target_land = next((l for l in believes.lands if l.stage == "PLANTING" and l.crop_type), None)
                    elif op == "CHECK":
                        target_land = next((l for l in believes.lands if l.stage == "GROWING" and l.crop_type), None)
                    elif op == "HARVEST":
                        target_land = next((l for l in believes.lands if l.stage == "HARVEST_READY" and l.crop_type), None)
                        if not target_land:
                            target_land = next((l for l in believes.lands if l.stage == "GROWING" and l.crop_type), None)
                    elif op == "DEFOREST":
                        target_land = next((l for l in believes.lands if l.stage in ("GROWING", "HARVEST_READY") and l.crop_type), None)
                    if target_land:
                        target_land.stage = new_stage
                        if op == "PLANT" and hasattr(believes, 'seeds'):
                            believes.seeds = max(0, believes.seeds - 1)
                        elif op == "PREPARE" and hasattr(believes, 'tools'):
                            believes.tools = max(0, believes.tools - 1)
                        elif op == "IRRIGATE" and hasattr(believes, 'water_available'):
                            believes.water_available = max(0, believes.water_available - 1)
                if op in ("PREPARE", "PLANT") and crop_type and believes.lands:
                    if op == "PREPARE":
                        target = next((l for l in believes.lands if l.stage == new_stage), believes.lands[0])
                    else:
                        target = next((l for l in believes.lands if l.stage == new_stage), believes.lands[0])
                    target.crop_type = crop_type

            crop_id = f"{agent}_crop"
            parcel_id = ""
            if target_land and hasattr(target_land, 'id') and target_land.id:
                crop_id = target_land.id
            if target_land and hasattr(target_land, 'parcel_name') and target_land.parcel_name:
                parcel_id = target_land.parcel_name
            msg = AgroEcosystemMessage(
                message_type=op_map.get(op, AgroEcosystemMessageType.CROP_INFORMATION),
                crop_id=crop_id,
                peasant_alias=agent,
                date=believes.current_date,
                crop_type=crop_type,
                parcel_id=parcel_id,
            )
            send_guard("AgroEcosystem", op, msg)


class SetLandCropTypeAction:
    def execute(self, believes: Any, params: dict[str, Any] | None = None) -> bool:
        p = params or {}
        crop_type = p.get("crop_type", "maiz")
        if hasattr(believes, 'lands') and believes.lands:
            target = next((l for l in believes.lands if l.stage in ("NONE", "FALLOW", "PLANTING")), believes.lands[0])
            target.crop_type = crop_type
        return True


ACTIONS: dict[str, PrimitiveAction] = {
    "emit_episode": EmitEpisodeAction(),
    "update_belief": UpdateBeliefAction(),
    "consume_resource": ConsumeResourceAction(),
    "send_event": SendEventAction(),
    "send_marketplace_event": SendMarketPlaceEventAction(),
    "send_civic_land_request": SendCivicAuthorityLandRequestAction(),
    "emit_emotion": EmitEmotionAction(),
    "increase_health": IncreaseHealthAction(),
    "sync_clock": SyncClockAction(),
    "log_audit": LogAuditAction(),
    "increment_belief": IncrementBeliefAction(),
    "wait_for_event": WaitForEventAction(),
    "conditional": ConditionalAction(),
    "send_society_collaboration": SendSocietyCollaborationAction(),
    "spend_friends_time": SpendFriendsTimeAction(),
    "agro_ecosystem_operation": AgroEcosystemAction(),
    "set_land_crop_type": SetLandCropTypeAction(),
}
