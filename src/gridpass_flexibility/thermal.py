"""Single-zone sensible heat balance with exact zero-order-hold discretization.

A lumped thermal model, not a CFD or equipment qualification model.
Temperatures are degrees Celsius; power is MW, capacitance MWh/K,
conductance MW/K. COP is thermal heat removed per electrical input.
"""
from __future__ import annotations
import math

SERIES_FIELDS=("baseline_cooling_mw","ambient_c","heat_gain_mw","cop")

def parameters(spec,n):
    from .dispatch import _number
    name=spec["id"]
    def series(key,lo,hi):
        value=spec[key]
        if not isinstance(value,list):value=[value]*n
        if len(value)!=n:raise ValueError(f"{name} {key}: expected {n} intervals")
        return [_number(x,f"{name} {key}",lo,hi) for x in value]
    p=_number(spec["power_mw"],name+" power")
    lower=_number(spec["min_temp_c"],name+" minimum temperature",0,100)
    upper=_number(spec["max_temp_c"],name+" maximum temperature",lower,100)
    initial=_number(spec["initial_temp_c"],name+" initial temperature",lower,upper)
    terminal=_number(spec.get("terminal_max_temp_c",initial),name+" terminal temperature",lower,upper)
    return {"capacitance":_number(spec["thermal_capacitance_mwh_per_k"],name+" thermal capacitance",1e-6,1e8),
            "conductance":_number(spec["thermal_conductance_mw_per_k"],name+" thermal conductance"),
            "lower":lower,"upper":upper,"initial":initial,"terminal":terminal,
            "baseline_cooling_mw":series("baseline_cooling_mw",0,p),
            "ambient_c":series("ambient_c",-100,100),
            "heat_gain_mw":series("heat_gain_mw",0,1e8),
            "cop":series("cop",.01,100)}

def coefficients(capacitance,conductance,dt):
    """Return decay and heat-input gain (K/MW), including zero conductance."""
    if conductance==0:return 1.0,dt/capacitance
    x=conductance*dt/capacitance
    return math.exp(-x),-math.expm1(-x)/conductance

def next_temperature(previous,ambient,heat_gain,cooling,cop,capacitance,conductance,dt):
    decay,gain=coefficients(capacitance,conductance,dt)
    return decay*previous+(1-decay)*ambient+gain*(heat_gain-cop*cooling)
