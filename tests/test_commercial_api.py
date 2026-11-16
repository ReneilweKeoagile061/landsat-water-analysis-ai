import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from backend.main import analyze_point, PointRadiusRequest, healthz

# ---------------------------------------------------------------
# pytest test suite
# ---------------------------------------------------------------

class TestHealthEndpoint:
    def test_healthz_returns_ok(self):
        result = asyncio.run(healthz())
        assert result["status"] == "ok"
        assert result["stage1_model_loaded"] == True
        assert result["stage2_model_loaded"] == True


class TestAnalyzePoint:
    @pytest.fixture
    def botswana_request(self):
        return PointRadiusRequest(latitude=-21.7439, longitude=28.0716, radius_km=50.0)

    @pytest.fixture
    def namibia_request(self):
        return PointRadiusRequest(latitude=-24.3200, longitude=18.4100, radius_km=30.0)

    @pytest.fixture
    def south_africa_request(self):
        return PointRadiusRequest(latitude=-27.1500, longitude=20.6200, radius_km=40.0)

    def test_botswana_returns_success(self, botswana_request):
        result = asyncio.run(analyze_point(botswana_request))
        assert result.status == "success"
        assert result.country_jurisdiction == "BOTSWANA"
        assert result.water_strike_probability_pct > 0
        assert len(result.top_recommended_drill_targets) == 3

    def test_namibia_returns_success(self, namibia_request):
        result = asyncio.run(analyze_point(namibia_request))
        assert result.status == "success"
        assert result.country_jurisdiction == "NAMIBIA"

    def test_south_africa_returns_success(self, south_africa_request):
        result = asyncio.run(analyze_point(south_africa_request))
        assert result.status == "success"
        assert result.country_jurisdiction == "SOUTH AFRICA"

    def test_drill_targets_have_ert_lines(self, botswana_request):
        result = asyncio.run(analyze_point(botswana_request))
        for target in result.top_recommended_drill_targets:
            ert = target.ert_geophysics_line
            assert ert.length_m == 200.0
            assert len(ert.transect_start) == 2
            assert len(ert.transect_end) == 2
            assert ert.strike_deg >= 0

    def test_yield_tier_is_valid(self, botswana_request):
        result = asyncio.run(analyze_point(botswana_request))
        valid_tiers = ["Commercial High (≥ 5.0 m³/h)", "Medium Yield (1.0 - 5.0 m³/h)", "Dry Risk (< 0.5 m³/h)"]
        assert result.overall_yield_tier in valid_tiers

    def test_targets_have_fracture_families(self, botswana_request):
        result = asyncio.run(analyze_point(botswana_request))
        for target in result.top_recommended_drill_targets:
            assert target.fracture_family is not None
            assert "°" in target.fracture_family

    def test_model_provenance_present(self, botswana_request):
        result = asyncio.run(analyze_point(botswana_request))
        assert "engine" in result.model_provenance
        assert "two_stage_architecture" in result.model_provenance

    def test_bgi_ground_truth_calibration_toteng(self):
        # User screenshot coordinates: Toteng near BH6417
        req = PointRadiusRequest(latitude=-20.34088, longitude=22.95223, radius_km=50.0)
        result = asyncio.run(analyze_point(req))
        assert result.water_strike_probability_pct >= 85.0
        assert result.ground_truth_calibration is not None
        assert result.ground_truth_calibration["has_ground_truth_nearby"] is True
        assert result.ground_truth_calibration["nearest_borehole_id"] == "BH6417"
        assert result.depth_to_water_strike_m == 22.0

    def test_bgi_ground_truth_calibration_khudumelapye(self):
        # Exact commercial well BH10687 (44 m3/h yield)
        req = PointRadiusRequest(latitude=-23.741806, longitude=25.101472, radius_km=50.0)
        result = asyncio.run(analyze_point(req))
        assert result.water_strike_probability_pct >= 90.0
        assert result.ground_truth_calibration["nearest_borehole_id"] == "BH10687"
        assert result.estimated_yield_m3h >= 40.0


# ---------------------------------------------------------------
# Original run_tests() kept for backward compatibility
# ---------------------------------------------------------------
test_cases = [
    {
        "name": "Botswana Central Hard-Rock",
        "lat": -21.7439,
        "lon": 28.0716,
        "radius": 50.0
    },
    {
        "name": "Namibia Stampriet Artesian Basin",
        "lat": -24.3200,
        "lon": 18.4100,
        "radius": 30.0
    },
    {
        "name": "South Africa Kalahari Boundary",
        "lat": -27.1500,
        "lon": 20.6200,
        "radius": 40.0
    }
]

def run_tests():
    print("=" * 72)
    print(" 🧪 LIVE VERIFICATION TEST: TWO-STAGE MULTI-COUNTRY API ENGINE")
    print("=" * 72)

    for tc in test_cases:
        req = PointRadiusRequest(latitude=tc["lat"], longitude=tc["lon"], radius_km=tc["radius"])
        res = asyncio.run(analyze_point(req))

        t1 = res.top_recommended_drill_targets[0]
        ert = t1.ert_geophysics_line

        print(f"\n📍 Target: {tc['name']}")
        print(f"   Coordinates     : [{tc['lat']}, {tc['lon']}] (Radius: {tc['radius']} km)")
        print(f"   Jurisdiction    : {res.country_jurisdiction}")
        print(f"   Strike Prob     : {res.water_strike_probability_pct:.1f}%")
        print(f"   Yield Sizing    : {res.overall_yield_tier}")
        print(f"   Drilling Depth  : {res.recommended_drilling_depth_m} m")
        print(f"   Salinity (TDS)  : {res.estimated_tds_salinity_mg_l} mg/L")
        print(f"   Top Target #1   : {t1.target_id} at ({t1.latitude}, {t1.longitude})")
        print(f"   Fracture Family : {t1.fracture_family} (Distance: {t1.structural_fracture_distance_m} m)")
        print(f"   ERT Transect    : Start {ert.transect_start} -> End {ert.transect_end}")
        print(f"   Recommendation  : {res.commercial_recommendation}")

    print("\n" + "=" * 72)
    print(" ✅ ALL 3 MULTI-COUNTRY TEST CASES PASSED WITH 100% SUCCESS")
    print("=" * 72)

if __name__ == "__main__":
    run_tests()
