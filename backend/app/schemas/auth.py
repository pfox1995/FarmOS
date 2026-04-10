from typing import Literal

from pydantic import BaseModel, Field

# 허용 값 — 프론트엔드 constants/farming.ts 와 동기화
FarmlandType = Literal["", "논", "밭", "과수원", "혼합"]
FarmerType = Literal["일반", "청년농업인", "후계농업경영인", "전업농업인"]


class SignupRequest(BaseModel):
    user_id: str = Field(min_length=4, max_length=10)
    name: str = Field(min_length=2, max_length=10)
    email: str
    password: str = Field(min_length=4)
    location: str = Field(default="", max_length=100)
    area: float = 0.0
    farmname: str = ""
    profile: str = ""


class OnboardingRequest(BaseModel):
    """온보딩 완료 시 농장 프로필 업데이트."""
    farmname: str = ""
    location: str = Field(default="", max_length=100)
    area: float = Field(default=0.0, ge=0)
    main_crop: str = Field(default="", max_length=40)
    crop_variety: str = Field(default="", max_length=40)
    farmland_type: FarmlandType = ""
    is_promotion_area: bool = False
    has_farm_registration: bool = False
    farmer_type: FarmerType = "일반"
    years_rural_residence: int = Field(default=0, ge=0, le=120)
    years_farming: int = Field(default=0, ge=0, le=120)


class LoginRequest(BaseModel):
    user_id: str
    password: str


class FindIdRequest(BaseModel):
    name: str
    email: str


class FindPasswordRequest(BaseModel):
    user_id: str
    email: str


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: str = Field(min_length=4)
    reset_token: str


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    location: str
    area: float
    farmname: str
    profile: str
    status: int
    onboarding_completed: bool = False
    main_crop: str = ""
    crop_variety: str = ""
    farmland_type: FarmlandType = ""
    is_promotion_area: bool = False
    has_farm_registration: bool = False
    farmer_type: FarmerType = "일반"
    years_rural_residence: int = 0
    years_farming: int = 0
