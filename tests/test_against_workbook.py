"""Every expected value here is the number MechEng_HandCalcs.xlsx computes for its
own default inputs. If a formula gets mistyped during a refactor, these catch it.
"""

import math

import pytest

from napkin import beams, bolts, columns, cooling, plates, pressure, sections, shafts, units


def close(actual, expected, rel=1e-9):
    assert actual == pytest.approx(expected, rel=rel)


class TestSections:
    def test_rectangle_1x2(self):
        s = sections.rectangle(b=1, h=2)
        close(s.A, 2)
        close(s.I, 0.666666666666667)
        close(s.S, 0.666666666666667)
        close(s.r, 0.577350269189626)

    def test_round_tube(self):
        s = sections.round_tube(od=1.5, id=1.25)
        close(s.A, 0.539961237335746)
        close(s.I, 0.128662638583908)
        close(s.S, 0.171550184778544)
        close(s.r, 0.488140604744166)

    def test_i_beam(self):
        s = sections.i_beam(H=4, B=3, tf=0.375, tw=0.25)
        close(s.A, 3.0625)
        close(s.I, 8.13313802083333)
        close(s.S, 4.06656901041667)
        close(s.r, 1.62963754786608)

    def test_tube_id_must_be_smaller(self):
        with pytest.raises(ValueError, match="must be less than"):
            sections.round_tube(od=1.0, id=1.5)


class TestBeams:
    def test_simply_supported_point_load(self):
        """Workbook default: L=20, P=500, A36, 1x1 rectangle."""
        r = beams.analyze("ss_point", L=20, section=sections.rectangle(1, 1),
                          material="Steel A36 (HR)", P=500)
        close(r.M, 2500)
        close(r.stress, 15000)
        close(r.deflection, 0.0344827586206897)
        close(r.sf, 2.4)

    @pytest.mark.parametrize("case,expected_M", [
        ("ss_point", 2500), ("ss_uniform", 500), ("cant_point", 10000),
        ("cant_uniform", 2000), ("fixed_point", 1250), ("fixed_uniform", 333.3333333333),
    ])
    def test_all_six_moments(self, case, expected_M):
        r = beams.analyze(case, L=20, section=sections.rectangle(1, 1),
                          material="Steel A36 (HR)", P=500, w=10)
        close(r.M, expected_M, rel=1e-6)

    def test_required_size_round_trips(self):
        """A beam sized for SF 2 should analyze back to SF 2."""
        M = 2500
        d = beams.required_diameter(M, "Steel A36 (HR)", target_sf=2.0)
        r = beams.analyze("ss_point", L=20, section=sections.solid_round(d),
                          material="Steel A36 (HR)", P=500)
        close(r.sf, 2.0, rel=1e-6)

    def test_deflection_limit_flagged(self):
        r = beams.analyze("cant_point", L=40, section=sections.rectangle(1, 1),
                          material="Al 6061-T6", P=500, deflection_limit=240)
        assert not r.deflection_ok
        assert any("Deflection" in w for w in r.warnings)

    def test_unknown_case_rejected(self):
        with pytest.raises(ValueError, match="Unknown case"):
            beams.analyze("nope", L=1, section=sections.rectangle(1, 1),
                          material="Al 6061-T6", P=1)


class TestPlates:
    def test_circular_clamped(self):
        """a=3, q=200, t=0.75, P20 tool steel, clamped."""
        r = plates.circular(a=3, q=200, t=0.75, material="Tool steel P20 (30 HRC)",
                            edge="clamped", target_sf=2)
        close(r.stress, 2400)
        close(r.deflection, 0.000222036363636364, rel=1e-6)
        close(r.sf, 52.0833333333333)
        close(r.required_t, 0.146969384566991, rel=1e-9)

    def test_rectangular_simply_supported(self):
        """a=8, b=4, q=100, t=0.5, A36, SS. a/b = 2 -> beta 0.6102, alpha 0.111."""
        r = plates.rectangular(a=8, b=4, q=100, t=0.5, material="Steel A36 (HR)",
                               edge="simply_supported", target_sf=2)
        close(r.stress, 3905.28)
        close(r.deflection, 0.000783889655172414, rel=1e-9)
        close(r.sf, 9.21828908554572)
        close(r.required_t, 0.232894826048154, rel=1e-9)

    def test_coefficient_lookup_steps_down(self):
        """VLOOKUP TRUE semantics: a/b of 1.9 uses the 1.8 row, not 2.0."""
        r19 = plates.rectangular(a=1.9, b=1, q=100, t=0.25, material="Steel A36 (HR)")
        r18 = plates.rectangular(a=1.8, b=1, q=100, t=0.25, material="Steel A36 (HR)")
        close(r19.stress, r18.stress)

    def test_large_deflection_warns(self):
        r = plates.circular(a=6, q=500, t=0.05, material="Al 6061-T6")
        assert not r.small_deflection_ok
        assert any("small-deflection" in w for w in r.warnings)


class TestColumns:
    def test_euler_regime(self):
        """L=30, P=2000, A36, 0.75 solid round, pinned-pinned."""
        r = columns.analyze(L=30, P=2000, section=sections.solid_round(0.75),
                            material="Steel A36 (HR)", end_condition="pinned_pinned")
        close(r.slenderness, 160)
        close(r.Cc, 126.099283554135)
        assert r.regime.startswith("Euler")
        close(r.critical_stress, 11180.411235609)
        close(r.Pcr, 4939.35437839249)
        close(r.sf, 2.46967718919624)

    def test_johnson_regime_for_stubby_column(self):
        r = columns.analyze(L=5, P=2000, section=sections.solid_round(0.75),
                            material="Steel A36 (HR)")
        assert r.regime.startswith("Johnson")
        assert r.slenderness < r.Cc

    def test_aisc_k_differs_from_theoretical(self):
        kw = dict(L=30, P=2000, section=sections.solid_round(0.75),
                  material="Steel A36 (HR)", end_condition="fixed_fixed")
        assert columns.analyze(**kw).sf > columns.analyze(**kw, use_aisc_k=True).sf


class TestShafts:
    def test_combined_loading(self):
        """5 HP at 1750 RPM, M=200, d=0.75, L=12, 4140."""
        r = shafts.analyze(d=0.75, material="Steel 4140 (Q&T 28 HRC)", M=200,
                           hp=5, rpm=1750, L=12)
        close(r.T, 180.071428571429)
        close(r.torsional_shear, 2173.85778947884)
        close(r.bending_stress, 4828.87886595854)
        close(r.von_mises, 6123.31970165976)
        close(r.sf, 15.514460232127)
        close(r.twist_deg, 0.346231834747305)

    def test_required_diameter(self):
        d = shafts.required_diameter(M=200, T=180.071428571429,
                                     material="Steel 4140 (Q&T 28 HRC)", target_sf=2)
        close(d, 0.37887187894011, rel=1e-9)

    def test_explicit_torque_overrides_power(self):
        r = shafts.analyze(d=0.75, material="Al 6061-T6", T=500, hp=5, rpm=1750)
        close(r.T, 500)

    def test_shear_modulus(self):
        r = shafts.analyze(d=0.75, material="Steel 4140 (Q&T 28 HRC)", M=200, T=180, L=12)
        from napkin.materials import get
        close(get("Steel 4140 (Q&T 28 HRC)").G, 11511627.9069767)


class TestBolts:
    def test_grade5_38_16(self):
        """3/8-16 SAE Gr 5, 0.75 preload, K=0.2, P=1000, C=0.25."""
        r = bolts.analyze("3/8-16", "SAE Gr 5", preload_fraction=0.75,
                          nut_factor=0.2, P=1000, C=0.25)
        close(r.Fp, 6587.5)
        close(r.Fi, 4940.625)
        close(r.torque_in_lbf, 370.546875)
        close(r.torque_ft_lbf, 30.87890625)
        close(r.Fb, 5190.625)
        close(r.sf_proof, 1.2691149909693)
        close(r.load_factor, 8.7575)
        close(r.separation_factor, 6.5875)

    def test_nut_factor_by_name(self):
        by_name = bolts.analyze("1/4-20", nut_factor="lubricated", P=0)
        by_value = bolts.analyze("1/4-20", nut_factor=0.12, P=0)
        close(by_name.torque_in_lbf, by_value.torque_in_lbf)

    def test_no_external_load_leaves_factors_undefined(self):
        r = bolts.analyze("1/4-20", P=0)
        assert r.separation_factor is None
        assert r.load_factor is None

    def test_unknown_thread_rejected(self):
        with pytest.raises(ValueError, match="Unknown thread"):
            bolts.analyze("M8-1.25")


class TestPressure:
    def test_cylinder(self):
        """ID=4, t=0.12, P=150, A36, target SF 3."""
        r = pressure.cylinder(ID=4, t=0.12, P=150, material="Steel A36 (HR)", target_sf=3)
        close(r.hoop_stress, 2500)
        close(r.longitudinal_stress, 1250)
        close(r.sf, 14.4)
        close(r.required_t, 0.025)
        assert r.thin_wall_valid

    def test_sphere_is_half_the_stress(self):
        cyl = pressure.cylinder(ID=4, t=0.12, P=150, material="Steel A36 (HR)")
        sph = pressure.sphere(ID=4, t=0.12, P=150, material="Steel A36 (HR)")
        close(sph.hoop_stress, cyl.hoop_stress / 2)

    def test_thick_wall_warns(self):
        r = pressure.cylinder(ID=4, t=1.0, P=150, material="Steel A36 (HR)")
        assert not r.thin_wall_valid
        assert any("thick-wall" in w for w in r.warnings)

    def test_end_cap_bolts(self):
        r = pressure.end_cap_bolts(ID=4, P=150, n_bolts=8)
        close(r.outputs[0][1], 1884.95559215388)
        close(r.outputs[1][1], 235.619449019234)


class TestCooling:
    def test_required_flow(self):
        r = cooling.required_flow(Q_btu_hr=20000, dT=4)
        close(r.outputs[0][1], 10)

    def test_watts_fallback(self):
        r = cooling.required_flow(Q_watts=1000, dT=4)
        close(r.outputs[0][1], 1000 * 3.412 / 2000)

    def test_circuit(self):
        """d=0.4375, 2 GPM, 10 ft, 100 F water, K=6, 8 psi pump."""
        r = cooling.circuit(d=0.4375, gpm=2, length_ft=10, water_temp_f=100,
                            roughness=0.0018, K_total=6, pump_psi=8)
        close(r.velocity, 4.26840816326531)
        close(r.reynolds, 21243.6974789916, rel=1e-9)
        close(r.friction_factor, 0.0334388491328467, rel=1e-9)
        close(r.pressure_drop, 1.86046748238485, rel=1e-9)
        close(r.margin, 6.13953251761515, rel=1e-9)
        assert "Fully turbulent" in r.regime

    def test_laminar_flagged(self):
        r = cooling.circuit(d=1.0, gpm=0.1, length_ft=5)
        assert "Laminar" in r.regime
        assert any("turbulent" in w for w in r.warnings)

    def test_viscosity_interpolates(self):
        close(cooling.viscosity_at(100), 0.68)
        close(cooling.viscosity_at(85), (0.95 + 0.68) / 2)
        close(cooling.viscosity_at(-40), 1.40)
        close(cooling.viscosity_at(500), 0.35)

    def test_conduction_and_convection(self):
        c = cooling.conduction("Tool steel P20 (30 HRC)", area_in2=10, thickness_in=1, dT=50)
        close(c.outputs[0][1], 17 * (10 / 144) * 50 / (1 / 12))
        v = cooling.convection(h=500, area_in2=10, dT=50)
        close(v.outputs[0][1], 500 * (10 / 144) * 50)


class TestUnits:
    @pytest.mark.parametrize("value,frm,to,expected", [
        (1, "in", "mm", 25.4), (25.4, "mm", "in", 1.0),
        (100, "lbf", "N", 444.822), (100, "psi", "MPa", 0.689476),
        (212, "F", "C", 100.0), (100, "C", "F", 212.0),
        (5, "HP", "kW", 3.7285),
    ])
    def test_conversions(self, value, frm, to, expected):
        close(units.convert(value, frm, to), expected, rel=1e-6)

    def test_round_trip(self):
        close(units.convert(units.convert(7.5, "psi", "kPa"), "kPa", "psi"), 7.5)

    def test_torque_from_power(self):
        close(units.torque_from_power(5, 1750), 180.071428571429)
        close(units.torque_from_power(0, 1750), 0)

    def test_unknown_conversion_rejected(self):
        with pytest.raises(ValueError, match="No conversion"):
            units.convert(1, "furlong", "mm")


class TestResultRendering:
    def test_markdown_has_the_pieces_a_design_record_needs(self):
        r = beams.analyze("ss_point", L=20, section=sections.rectangle(1, 1),
                          material="Steel A36 (HR)", P=500)
        md = r.markdown()
        assert md.startswith("### ")
        assert "| Input | Value | Unit |" in md
        assert "| Result | Value | Unit |" in md
        assert "σ = M/S" in md
        assert "Shigley" in md

    def test_safety_factor_classification(self):
        from napkin import classify_sf
        assert classify_sf(0.9) == "FAIL"
        assert classify_sf(1.2) == "MARGINAL"
        assert classify_sf(2.0) == "OK"
        assert classify_sf(None) == "n/a"
