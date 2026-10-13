"""Parameter sets for ``example_idf.idf`` (the small office reference building), written for bdopt.

This is the same selection of 4, 7 or 11 parameters that the course notebook used, picked by Morris screening in a
small-scale sensitivity analysis. Each design variable is a bdopt ``Parameter`` made of a ``FieldSelector`` (where the
value goes in the model) and a ``RangeParameter`` (which values are allowed), and has a **unique name**: bdopt does
not accept two parameters with the same name, and the set of 11 has two thicknesses and two conductivities.

``expand_plist`` of the previous toolbox found the class of an object by its name; here the class is written.
The window-to-wall ratio comes from ``window_to_wall.py`` (a geometry edit written as a ``GenericSelector``). It
only makes the windows of the model grow in place, and on ``example_idf.idf`` they stop fitting above 0.46 (the glass
door of the south wall is in the way), so its range here is 0.1 to 0.45. The previous toolbox accepted any value
between 0.01 and 0.99 for this variable, but it was a fraction of the size of the existing window, not of the wall.
"""

from bdopt import FieldSelector, Parameter, RangeParameter

from window_to_wall import wwr


def _range(class_name, object_name, field_name, low, high, name):
    return Parameter(FieldSelector(class_name, object_name, field_name), RangeParameter(low, high), name=name)


def parameter_set(number_of_pars=4):
    """The parameters of the set with ``number_of_pars`` design variables (4, 7 or 11)."""
    window = "NonRes Fixed Assembly Window"
    wall_ins = "Mass NonRes Wall Insulation"
    attic_ins = "AtticFloor NonRes Insulation"

    equipment = _range("ElectricEquipment", "*", "Watts per Zone Floor Area", 10, 15, "Equipment W/m2")
    lights = _range("Lights", "*", "Watts per Zone Floor Area", 10, 15, "Lights W/m2")
    window_ratio = wwr(0.1, 0.45)       # window area / wall area; see window_to_wall.py for the limit

    if number_of_pars == 4:
        return [
            _range("WindowMaterial:SimpleGlazingSystem", window, "Solar Heat Gain Coefficient", 0.01, 0.99, "Window SHGC"),
            equipment, lights, window_ratio,
        ]
    if number_of_pars == 7:
        return [
            _range("Material", wall_ins, "Conductivity", 0.02, 0.2, "Wall insulation conductivity"),
            _range("Material", attic_ins, "Thickness", 0.1, 0.3, "Attic insulation thickness"),
            _range("WindowMaterial:SimpleGlazingSystem", window, "U-Factor", 0.1, 5, "Window U-factor"),
            _range("WindowMaterial:SimpleGlazingSystem", window, "Solar Heat Gain Coefficient", 0.01, 0.99, "Window SHGC"),
            equipment, lights, window_ratio,
        ]
    if number_of_pars == 11:
        return [
            _range("Material", wall_ins, "Thickness", 0.01, 0.5, "Wall insulation thickness"),
            _range("Material", wall_ins, "Conductivity", 0.02, 0.2, "Wall insulation conductivity"),
            _range("Material", attic_ins, "Thickness", 0.1, 0.3, "Attic insulation thickness"),
            _range("WindowMaterial:SimpleGlazingSystem", window, "U-Factor", 0.1, 5, "Window U-factor"),
            _range("WindowMaterial:SimpleGlazingSystem", window, "Solar Heat Gain Coefficient", 0.01, 0.99, "Window SHGC"),
            _range("Building", "Ref Bldg Small Office New2004_v1.3_5.0", "North Axis", 0, 360, "North axis"),
            _range("WaterHeater:Mixed", "SWHSys1 Water Heater", "Heater Thermal Efficiency", 0.7, 0.95, "Water heater efficiency"),
            equipment, lights,
            _range("Coil:Heating:Fuel", "*", "Burner Efficiency", 0.7, 0.9, "Burner efficiency"),
            window_ratio,
        ]
    raise ValueError("number_of_pars must be 4, 7 or 11")
