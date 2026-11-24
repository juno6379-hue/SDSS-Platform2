"""기후 feature의 시공간 결합 계획. 기후 수치를 생성하거나 추정하지 않는다."""

from .climate_join import BoundaryVersion, FeatureJoinRequest, plan_climate_join

__all__ = ["BoundaryVersion", "FeatureJoinRequest", "plan_climate_join"]
