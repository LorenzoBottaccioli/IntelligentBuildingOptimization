"""Read the current model state straight from the in-memory IDF.

The SQL tables were a second copy of what the IDF already says, and the two
drifted apart the moment anything wrote to one and not the other. The IDF is the
artefact that gets converted to an FMU, so it is the only source of truth worth
having; these readers return the same JSON shapes the frontend already consumes.

`id` is derived from what names the object in the IDF, not from its position, so
it survives adding and removing siblings -- see _ident().
"""



def _ident(*parts):
    """Stable identifier for one object, derived from what names it in the IDF.

    This is what the frontend keys its observation/reward choices on. A positional
    index would look fine until the student adds or removes an object: every later
    index shifts by one and their tagging silently re-maps onto different
    variables. Deriving the id from the object's own name keeps a choice attached
    to the thing it was made about.
    """
    return '|'.join(str(p).strip().upper() for p in parts if p is not None)


def _lines(obj, prefix, limit=500):
    """Collect repeating numbered fields (Program_Line_1, Program_Name_1, ...)."""
    out = []
    for i in range(1, limit):
        field = f'{prefix}{i}'
        if not hasattr(obj, field):
            break
        value = getattr(obj, field)
        if value in (None, ''):
            break
        out.append(value)
    return out


def output_variables(idf):
    return [{
        'id': _ident(o.Key_Value, o.Variable_Name, o.Reporting_Frequency),
        'keyValue': o.Key_Value,
        'variableName': o.Variable_Name,
        'reportingFrequency': o.Reporting_Frequency,
        'scheduleName': getattr(o, 'Schedule_Name', ''),
    } for o in idf.idfobjects['Output:Variable']]


def output_meters(idf):
    return [{
        'id': _ident(o.Key_Name),
        'keyName': o.Key_Name,
        'reportingFrequency': o.Reporting_Frequency,
    } for o in idf.idfobjects['Output:Meter']]


def ems_sensors(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'outputVariableOrOutputMeterIndexKeyName':
            o.OutputVariable_or_OutputMeter_Index_Key_Name,
        'outputVariableOrOutputMeterName': o.OutputVariable_or_OutputMeter_Name,
    } for o in idf.idfobjects['EnergyManagementSystem:Sensor']]


def ems_actuators(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'actuatedComponentUniqueName': o.Actuated_Component_Unique_Name,
        'actuatedComponentType': o.Actuated_Component_Type,
        'actuatedComponentControlType': o.Actuated_Component_Control_Type,
    } for o in idf.idfobjects['EnergyManagementSystem:Actuator']]


def ems_output_variables(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'variableName': o.EMS_Variable_Name,
        'typeOfData': o.Type_of_Data_in_Variable,
        'updateFrequency': o.Update_Frequency,
        'emsProgramOrSub': getattr(o, 'EMS_Program_or_Subroutine_Name', ''),
        'units': getattr(o, 'Units', ''),
    } for o in idf.idfobjects['EnergyManagementSystem:OutputVariable']]


def ems_programs(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'programLines': _lines(o, 'Program_Line_'),
    } for o in idf.idfobjects['EnergyManagementSystem:Program']]


def ems_program_calling_managers(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'energyPlusModelCallingPoint': o.EnergyPlus_Model_Calling_Point,
        'programNames': _lines(o, 'Program_Name_'),
    } for o in idf.idfobjects['EnergyManagementSystem:ProgramCallingManager']]


def fmu_from_variables(idf):
    return [{
        'id': _ident(o.FMU_Variable_Name),
        'outputVariableIndexKeyName': o.OutputVariable_Index_Key_Name,
        'outputVariableName': o.OutputVariable_Name,
        'fmuVariableName': o.FMU_Variable_Name,
    } for o in idf.idfobjects[
        'ExternalInterface:FunctionalMockupUnitExport:From:Variable']]


def fmu_to_variables(idf):
    return [{
        'id': _ident(o.FMU_Variable_Name),
        'name': o.Name,
        'fmuVariableName': o.FMU_Variable_Name,
        'initialValue': o.Initial_Value,
    } for o in idf.idfobjects[
        'ExternalInterface:FunctionalMockupUnitExport:To:Variable']]


def fmu_actuators(idf):
    return [{
        'id': _ident(o.FMU_Variable_Name),
        'name': o.Name,
        'actuatedComponentUniqueName': o.Actuated_Component_Unique_Name,
        'actuatedComponentType': o.Actuated_Component_Type,
        'actuatedComponentControlType': o.Actuated_Component_Control_Type,
        'fmuVariableName': o.FMU_Variable_Name,
        'initialValue': o.Initial_Value,
    } for o in idf.idfobjects[
        'ExternalInterface:FunctionalMockupUnitExport:To:Actuator']]


def fmu_schedules(idf):
    return [{
        'id': _ident(o.FMU_Variable_Name),
        'scheduleName': o.Schedule_Name,
        'scheduleTypeLimitsNames': o.Schedule_Type_Limits_Names,
        'fmuVariableName': o.FMU_Variable_Name,
        'initialValue': o.Initial_Value,
    } for o in idf.idfobjects[
        'ExternalInterface:FunctionalMockupUnitExport:To:Schedule']]


def schedule_type_limits(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'lowerLimitValue': getattr(o, 'Lower_Limit_Value', ''),
        'upperLimitValue': getattr(o, 'Upper_Limit_Value', ''),
    } for o in idf.idfobjects['ScheduleTypeLimits']]


SCHEDULE_CLASSES = (
    'Schedule:Day:Hourly', 'Schedule:Day:Interval', 'Schedule:Day:List',
    'Schedule:Week:Daily', 'Schedule:Week:Compact', 'Schedule:Year',
    'Schedule:Compact', 'Schedule:Constant', 'Schedule:File',
)


def schedule_names(idf):
    names, seen = [], set()
    for cls in SCHEDULE_CLASSES:
        for o in idf.idfobjects[cls]:
            if o.Name and o.Name not in seen:
                seen.add(o.Name)
                names.append({'id': _ident(o.Name), 'scheduleName': o.Name})
    return names


def zone_names(idf):
    return [z.Name for z in idf.idfobjects['Zone']]


def runperiod(idf):
    periods = idf.idfobjects['RunPeriod']
    if not periods:
        return []
    p = periods[0]
    return [{
        'id': 'runperiod',
        'beginMonth': p.Begin_Month,
        'beginDayOfMonth': p.Begin_Day_of_Month,
    }]


_SNAPSHOT_KEYS = (
    'current_idf_runperiod',
    'current_output_variables',
    'current_output_meters',
    'current_ems_sensors',
    'current_ems_actuators',
    'current_ems_output_variables',
    'current_ems_programs',
    'current_ems_program_calling_managers',
    'current_fmu_from_variables',
    'current_fmu_to_variables',
    'current_fmu_actuators',
    'current_fmu_schedules',
    'existing_schedule_type_limits',
    'existing_schedule_names',
    'zone_names',
)


def empty_snapshot():
    """Same keys as snapshot(), all empty — used before a model is loaded so the
    frontend never has to distinguish 'absent' from 'empty'."""
    return {key: [] for key in _SNAPSHOT_KEYS}


def snapshot(idf):
    """Everything get_objects reports about the model itself."""
    return {
        'current_idf_runperiod': runperiod(idf),
        'current_output_variables': output_variables(idf),
        'current_output_meters': output_meters(idf),
        'current_ems_sensors': ems_sensors(idf),
        'current_ems_actuators': ems_actuators(idf),
        'current_ems_output_variables': ems_output_variables(idf),
        'current_ems_programs': ems_programs(idf),
        'current_ems_program_calling_managers': ems_program_calling_managers(idf),
        'current_fmu_from_variables': fmu_from_variables(idf),
        'current_fmu_to_variables': fmu_to_variables(idf),
        'current_fmu_actuators': fmu_actuators(idf),
        'current_fmu_schedules': fmu_schedules(idf),
        'existing_schedule_type_limits': schedule_type_limits(idf),
        'existing_schedule_names': schedule_names(idf),
        'zone_names': zone_names(idf),
    }


# --------------------------------------------------------------------------- #
# Design-stage objects, consumed by the Surrogate Modeling panel.
#
# Two key styles, both kept as the frontend already expects them: explicit
# camelCase for the classes that had hand-written serialisers, and lowercased
# field names for the three that were dumped straight from their table columns.
# --------------------------------------------------------------------------- #

# The old SQL columns did not always match eppy's field names, and the panel
# still reads the column spellings. Alias the ones that differ, or those fields
# render as "undefined" in the object view.
_FIELD_ALIASES = {
    'zone_or_zonelist_name': 'zone_name',
    'zone_or_zonelist_or_space_or_spacelist_name': 'zone_or_space_name',
    'flow_rate_per_zone_floor_area': 'flow_per_zone_floor_area',
    'minimum_indoor_temperature_schedule_name': 'minimum_indoor_temp_schedule',
    'maximum_indoor_temperature_schedule_name': 'maximum_indoor_temp_schedule',
    'minimum_outdoor_temperature_schedule_name': 'minimum_outdoor_temp_schedule',
    'maximum_outdoor_temperature_schedule_name': 'maximum_outdoor_temp_schedule',
    'delta_temperature_schedule_name': 'delta_temp_schedule',
    'enduse_subcategory': 'end_use_subcategory',
    'shading_control_sequence_number': 'shading_control_sequence',
    'type_of_slat_angle_control_for_blinds': 'slat_angle_control_type',
}


def _lower_fields(obj, skip=('key',)):
    """Every field of an eppy object, keyed as the panel expects."""
    out = {}
    for f in obj.fieldnames:
        key = f.lower()
        if key in skip:
            continue
        value = getattr(obj, f, '')
        out[key] = value
        alias = _FIELD_ALIASES.get(key)
        if alias:
            out[alias] = value
    return out


def materials(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'roughness': o.Roughness,
        'thickness': o.Thickness,
        'conductivity': o.Conductivity,
        'density': o.Density,
        'specificHeat': o.Specific_Heat,
        'thermalAbsorptance': o.Thermal_Absorptance,
        'solarAbsorptance': o.Solar_Absorptance,
        'visibleAbsorptance': o.Visible_Absorptance,
    } for o in idf.idfobjects['Material']]


def constructions(idf):
    return [{
        'id': _ident(o.Name),
        'name': o.Name,
        'outsideLayer': o.Outside_Layer,
        'layers': [getattr(o, 'Layer_{}'.format(i), '') if i > 1 else o.Outside_Layer
                   for i in range(1, 11)],
    } for o in idf.idfobjects['Construction']]


def fenestration_surfaces(idf):
    out = []
    for o in idf.idfobjects['FenestrationSurface:Detailed']:
        vertices = []
        for i in range(1, 5):
            x = getattr(o, 'Vertex_{}_Xcoordinate'.format(i), '')
            if x == '' or x is None:
                break
            vertices.append({'x': x,
                             'y': getattr(o, 'Vertex_{}_Ycoordinate'.format(i), ''),
                             'z': getattr(o, 'Vertex_{}_Zcoordinate'.format(i), '')})
        out.append({
            'id': _ident(o.Name),
            'name': o.Name,
            'surfaceType': o.Surface_Type,
            'constructionName': o.Construction_Name,
            'buildingSurfaceName': o.Building_Surface_Name,
            'outsideBoundaryConditionObject': o.Outside_Boundary_Condition_Object,
            'viewFactorToGround': o.View_Factor_to_Ground,
            'frameAndDividerName': getattr(o, 'Frame_and_Divider_Name', ''),
            'multiplier': o.Multiplier,
            'vertices': vertices,
        })
    return out


def zone_ventilations(idf):
    return [dict(_lower_fields(o), id=_ident(o.Name))
            for o in idf.idfobjects['ZoneVentilation:DesignFlowRate']]


def lights(idf):
    return [dict(_lower_fields(o), id=_ident(o.Name))
            for o in idf.idfobjects['Lights']]


def window_shading_controls(idf):
    return [dict(_lower_fields(o), id=_ident(o.Name))
            for o in idf.idfobjects['WindowShadingControl']]
