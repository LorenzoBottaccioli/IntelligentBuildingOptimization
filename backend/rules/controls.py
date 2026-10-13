"""Rules from: Group - Thermal Zone Description/Geometry (WindowShadingControl),
Group - Zone Controls - Thermostats and Humidistats, Group Setpoint Managers,
Group Controllers, Group System Availability Managers, Group Demand Limiting
Controls, Group - Energy Management System (EMS), Group ExternalInterface,
Application Guide for EMS - Thermal Envelope (Window Shading Control actuator).
EnergyPlus 9.6 Input Output Reference (https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/)
and Application Guide for EMS. Field names verified against C:/EnergyPlusV9-6-0/Energy+.idd.
"""

GATED = {
    # --- WindowShadingControl ---
    ('WindowShadingControl', 'Schedule_Name'): {
        'by': 'Shading_Control_Is_Scheduled', 'when': ('Yes',),
        'note': 'Required if Shading_Control_Is_Scheduled = Yes; if No, Schedule_Name is not used.'},
    ('WindowShadingControl', 'Shading_Control_Is_Scheduled'): {
        'by': 'Shading_Control_Type', 'when': ('OnIfScheduleAllows',),
        'note': 'Must be Yes when Shading_Control_Type = OnIfScheduleAllows; must be blank/No for OnIfHighGlare.'},
    ('WindowShadingControl', 'Glare_Control_Is_Active'): {
        'by': 'Shading_Control_Type', 'when': ('OnIfHighGlare',),
        'note': 'Must be Yes when Shading_Control_Type = OnIfHighGlare; glare test is otherwise optional (OR-ed with the main test) for other control types.'},
    ('WindowShadingControl', 'Setpoint'): {
        'by': 'Shading_Control_Type',
        'when': ('OnIfHighSolarOnWindow', 'OnIfHighHorizontalSolar', 'OnIfHighOutdoorAirTemperature',
                  'OnIfHighZoneAirTemperature', 'OnIfHighZoneCooling', 'OnNightIfLowOutdoorTempAndOffDay',
                  'OnNightIfLowInsideTempAndOffDay', 'OnNightIfHeatingAndOffDay',
                  'OnNightIfLowOutdoorTempAndOnDayIfCooling', 'OnNightIfHeatingAndOnDayIfCooling',
                  'OffNightAndOnDayIfCoolingAndHighSolarOnWindow', 'OnNightAndOnDayIfCoolingAndHighSolarOnWindow',
                  'OnIfHighOutdoorAirTempAndHighSolarOnWindow', 'OnIfHighOutdoorAirTempAndHighHorizontalSolar',
                  'OnIfHighZoneAirTempAndHighSolarOnWindow', 'OnIfHighZoneAirTempAndHighHorizontalSolar'),
        'note': 'Unused for AlwaysOn, AlwaysOff, OnIfScheduleAllows, OnIfHighGlare and MeetDaylightIlluminanceSetpoint.'},
    ('WindowShadingControl', 'Setpoint_2'): {
        'by': 'Shading_Control_Type',
        'when': ('OnIfHighOutdoorAirTempAndHighSolarOnWindow', 'OnIfHighOutdoorAirTempAndHighHorizontalSolar',
                  'OnIfHighZoneAirTempAndHighSolarOnWindow', 'OnIfHighZoneAirTempAndHighHorizontalSolar'),
        'note': 'Only used as the second setpoint for these four two-setpoint control types; Setpoint holds the first (outdoor/zone air temp), Setpoint 2 holds the second (solar).'},
    ('WindowShadingControl', 'Construction_with_Shading_Name'): {
        'by': 'Shading_Type', 'when': ('SwitchableGlazing', 'BetweenGlassShade', 'BetweenGlassBlind'),
        'note': 'Required (no alternative) if Shading_Type = SwitchableGlazing, BetweenGlassShade or BetweenGlassBlind. For other Shading_Type values, Shading_Device_Material_Name may be given instead; if both are given, Construction_with_Shading_Name takes precedence.'},
    ('WindowShadingControl', 'Shading_Device_Material_Name'): {
        'by': 'Shading_Type', 'when': ('InteriorShade', 'ExteriorShade', 'ExteriorScreen', 'InteriorBlind', 'ExteriorBlind'),
        'note': 'Required if Construction_with_Shading_Name is not specified. Not applicable (must be blank) if Shading_Type = BetweenGlassShade, BetweenGlassBlind or SwitchableGlazing.'},
    ('WindowShadingControl', 'Type_of_Slat_Angle_Control_for_Blinds'): {
        'by': 'Shading_Type', 'when': ('InteriorBlind', 'ExteriorBlind', 'BetweenGlassBlind'),
        'note': 'Only applies when Shading_Type is a blind type.'},
    ('WindowShadingControl', 'Slat_Angle_Schedule_Name'): {
        'by': 'Type_of_Slat_Angle_Control_for_Blinds', 'when': ('ScheduledSlatAngle',),
        'note': 'Required if Type_of_Slat_Angle_Control_for_Blinds = ScheduledSlatAngle; also only meaningful when Shading_Type is a blind type.'},
    ('WindowShadingControl', 'Fenestration_Surface_2_Name'): {
        'by': 'Multiple_Surface_Control_Type', 'when': ('Sequential', 'Group'),
        'note': 'Extensible list of controlled windows; when Multiple_Surface_Control_Type = Sequential the surfaces are deployed in the listed order, when = Group they are deployed simultaneously.'},

    # --- Zone Controls - Thermostats ---
    ('ZoneControl:Thermostat', 'Control_1_Name'): {
        'by': 'Control_Type_Schedule_Name', 'when': ('1', '2', '3', '4'),
        'note': 'Control_Type_Schedule_Name selects, per timestep, which Control <x> Object Type/Name pair is active: 0=Uncontrolled(no thermostat), 1=ThermostatSetpoint:SingleHeating, 2=ThermostatSetpoint:SingleCooling, 3=ThermostatSetpoint:SingleHeatingOrCooling, 4=ThermostatSetpoint:DualSetpoint. Only one Control <x> pair per control type may be defined.'},
    ('ZoneControl:Thermostat:ThermalComfort', 'Thermal_Comfort_Control_1_Name'): {
        'by': 'Thermal_Comfort_Control_Type_Schedule_Name', 'when': ('1', '2', '3', '4'),
        'note': 'Same 0-4 control-type-schedule pattern as ZoneControl:Thermostat, but selecting Fanger-comfort-based setpoint objects.'},
    ('ZoneControl:Thermostat:OperativeTemperature', 'Fixed_Radiative_Fraction'): {
        'by': 'Radiative_Fraction_Input_Mode', 'when': ('Constant',),
        'note': 'Used only when Radiative_Fraction_Input_Mode = Constant.'},
    ('ZoneControl:Thermostat:OperativeTemperature', 'Radiative_Fraction_Schedule_Name'): {
        'by': 'Radiative_Fraction_Input_Mode', 'when': ('Scheduled',),
        'note': 'Used only when Radiative_Fraction_Input_Mode = Scheduled.'},
    ('ZoneControl:Thermostat:TemperatureAndHumidity', 'Overcool_Constant_Range'): {
        'by': 'Overcool_Range_Input_Method', 'when': ('Constant',),
        'note': 'Used only when Overcool_Range_Input_Method = Constant.'},
    ('ZoneControl:Thermostat:TemperatureAndHumidity', 'Overcool_Range_Schedule_Name'): {
        'by': 'Overcool_Range_Input_Method', 'when': ('Scheduled',),
        'note': 'Used only when Overcool_Range_Input_Method = Scheduled.'},
    ('ZoneControl:Thermostat:ThermalComfort', 'Averaging_Method_Specific_Object_Name'): {
        'by': 'Thermal_Comfort_Control_Averaging_Method', 'when': ('SpecificObject',),
        'note': 'Used only when Averaging Method = SpecificObject (docs refer to it as "Object Name for Specific Object Averaging Method").'},

    # --- SetpointManager ---
    ('SetpointManager:Scheduled:DualSetpoint', 'High_Setpoint_Schedule_Name'): {
        'by': 'Control_Variable', 'when': ('Temperature',), 'note': 'Control_Variable is restricted to Temperature for this object; both High and Low Setpoint Schedule Name are always required together.'},
    ('SetpointManager:OutdoorAirReset', 'Setpoint_at_Outdoor_Low_Temperature_2'): {
        'by': 'Schedule_Name', 'when': ('<specified>',),
        'note': 'The second reset rule (Setpoint_at_Outdoor_Low_Temperature_2, Outdoor_Low_Temperature_2, Setpoint_at_Outdoor_High_Temperature_2, Outdoor_High_Temperature_2) is only used when an optional Schedule_Name selecting rule 1 or 2 is supplied.'},
    ('SetpointManager:OutdoorAirPretreat', 'Minimum_Setpoint_Temperature'): {
        'by': 'Control_Variable', 'when': ('Temperature', 'MaximumTemperature', 'MinimumTemperature'),
        'note': 'Temperature-family Control_Variable choices gate the Minimum/Maximum_Setpoint_Temperature fields.'},
    ('SetpointManager:OutdoorAirPretreat', 'Minimum_Setpoint_Humidity_Ratio'): {
        'by': 'Control_Variable', 'when': ('HumidityRatio', 'MaximumHumidityRatio', 'MinimumHumidityRatio'),
        'note': 'Humidity-family Control_Variable choices gate the Minimum/Maximum_Setpoint_Humidity_Ratio fields instead of the temperature fields.'},
    ('SetpointManager:MixedAir', 'Minimum_Temperature_at_Cooling_Coil_Outlet_Node'): {
        'by': 'Cooling_Coil_Inlet_Node_Name', 'when': ('<specified>',),
        'note': 'Only relevant when the optional Cooling_Coil_Inlet_Node_Name / Cooling_Coil_Outlet_Node_Name pair is supplied.'},

    # --- Controllers ---
    ('Controller:OutdoorAir', 'Economizer_Maximum_Limit_DryBulb_Temperature'): {
        'by': 'Economizer_Control_Type', 'when': ('FixedDryBulb', 'FixedDewPointAndDryBulb'),
        'note': 'Dry-bulb limit is used by FixedDryBulb and the dry-bulb part of FixedDewPointAndDryBulb.'},
    ('Controller:OutdoorAir', 'Economizer_Maximum_Limit_Enthalpy'): {
        'by': 'Economizer_Control_Type', 'when': ('FixedEnthalpy',),
        'note': 'Used only when Economizer_Control_Type = FixedEnthalpy.'},
    ('Controller:OutdoorAir', 'Humidistat_Control_Zone_Name'): {
        'by': 'High_Humidity_Control', 'when': ('Yes',),
        'note': 'Required when High_Humidity_Control = Yes; also gates High_Humidity_Outdoor_Air_Flow_Ratio and Control_High_Indoor_Humidity_Based_on_Outdoor_Humidity_Ratio.'},
    ('ZoneHVAC:EnergyRecoveryVentilator:Controller', 'Humidistat_Control_Zone_Name'): {
        'by': 'High_Humidity_Control_Flag', 'when': ('Yes',),
        'note': 'Required when High_Humidity_Control_Flag = Yes; also gates High_Humidity_Outdoor_Air_Flow_Ratio.'},

    # --- System Availability Managers ---
    ('AvailabilityManager:NightCycle', 'Control_Zone_or_Zone_List_Name'): {
        'by': 'Control_Type', 'when': ('CycleOnControlZone',), 'note': 'Required only when Control_Type = CycleOnControlZone.'},
    ('AvailabilityManager:NightCycle', 'Cooling_Control_Zone_or_Zone_List_Name'): {
        'by': 'Control_Type', 'when': ('CycleOnAnyCoolingOrHeatingZone', 'CycleOnAnyCoolingZone'),
        'note': 'Required when Control_Type = CycleOnAnyCoolingOrHeatingZone or CycleOnAnyCoolingZone.'},
    ('AvailabilityManager:NightCycle', 'Heating_Control_Zone_or_Zone_List_Name'): {
        'by': 'Control_Type', 'when': ('CycleOnAnyCoolingOrHeatingZone', 'CycleOnAnyHeatingZone'),
        'note': 'Required when Control_Type = CycleOnAnyCoolingOrHeatingZone or CycleOnAnyHeatingZone.'},
    ('AvailabilityManager:NightCycle', 'Heating_Zone_Fans_Only_Zone_List_Name'): {
        'by': 'Control_Type', 'when': ('CycleOnAnyCoolingOrHeatingZone', 'CycleOnAnyHeatingZone', 'CycleOnAnyHeatingZoneFansOnly'),
        'note': 'Required for these three Control_Type values.'},
    ('AvailabilityManager:NightCycle', 'Cycling_Run_Time'): {
        'by': 'Cycling_Run_Time_Control_Type', 'when': ('FixedRunTime', 'ThermostatWithMinimumRunTime'),
        'note': 'Not used when Cycling_Run_Time_Control_Type = Thermostat (runs until setpoint is met instead).'},
    ('AvailabilityManager:OptimumStart', 'Control_Zone_Name'): {
        'by': 'Control_Type', 'when': ('ControlZone',), 'note': 'Required when Control_Type = ControlZone.'},
    ('AvailabilityManager:OptimumStart', 'Zone_List_Name'): {
        'by': 'Control_Type', 'when': ('MaximumofZoneList',), 'note': 'Required when Control_Type = MaximumofZoneList.'},
    ('AvailabilityManager:OptimumStart', 'Constant_Temperature_Gradient_during_Cooling'): {
        'by': 'Control_Algorithm', 'when': ('ConstantTemperatureGradient',), 'note': 'Required when Control_Algorithm = ConstantTemperatureGradient.'},
    ('AvailabilityManager:OptimumStart', 'Constant_Temperature_Gradient_during_Heating'): {
        'by': 'Control_Algorithm', 'when': ('ConstantTemperatureGradient',), 'note': 'Required when Control_Algorithm = ConstantTemperatureGradient.'},
    ('AvailabilityManager:OptimumStart', 'Initial_Temperature_Gradient_during_Cooling'): {
        'by': 'Control_Algorithm', 'when': ('AdaptiveTemperatureGradient',), 'note': 'Required when Control_Algorithm = AdaptiveTemperatureGradient.'},
    ('AvailabilityManager:OptimumStart', 'Initial_Temperature_Gradient_during_Heating'): {
        'by': 'Control_Algorithm', 'when': ('AdaptiveTemperatureGradient',), 'note': 'Required when Control_Algorithm = AdaptiveTemperatureGradient.'},
    ('AvailabilityManager:OptimumStart', 'Number_of_Previous_Days'): {
        'by': 'Control_Algorithm', 'when': ('AdaptiveTemperatureGradient',), 'note': 'Required when Control_Algorithm = AdaptiveTemperatureGradient.'},
    ('AvailabilityManager:OptimumStart', 'Constant_Start_Time'): {
        'by': 'Control_Algorithm', 'when': ('ConstantStartTime',), 'note': 'Required when Control_Algorithm = ConstantStartTime.'},
    ('AvailabilityManager:HybridVentilation', 'Minimum_Outdoor_Ventilation_Air_Schedule_Name'): {
        'by': 'Ventilation_Control_Mode_Schedule_Name', 'when': ('4',), 'note': 'Used only when the ventilation control mode schedule value is 4 (Outdoor Ventilation Air Control, AirflowNetwork only).'},

    # --- Demand Limiting Controls ---
    ('DemandManager:ExteriorLights', 'Maximum_Limit_Fraction'): {
        'by': 'Limit_Control', 'when': ('Fixed',), 'note': 'Used only when Limit_Control = Fixed.'},
    ('DemandManager:ExteriorLights', 'Rotation_Duration'): {
        'by': 'Selection_Control', 'when': ('RotateOne', 'RotateMany'), 'note': 'Used only when Selection_Control = RotateOne or RotateMany.'},
    ('DemandManager:Lights', 'Maximum_Limit_Fraction'): {
        'by': 'Limit_Control', 'when': ('Fixed',), 'note': 'Used only when Limit_Control = Fixed.'},
    ('DemandManager:Lights', 'Rotation_Duration'): {
        'by': 'Selection_Control', 'when': ('RotateOne', 'RotateMany'), 'note': 'Used only when Selection_Control = RotateOne or RotateMany.'},
    ('DemandManager:ElectricEquipment', 'Maximum_Limit_Fraction'): {
        'by': 'Limit_Control', 'when': ('Fixed',), 'note': 'Used only when Limit_Control = Fixed.'},
    ('DemandManager:ElectricEquipment', 'Rotation_Duration'): {
        'by': 'Selection_Control', 'when': ('RotateOne', 'RotateMany'), 'note': 'Used only when Selection_Control = RotateOne or RotateMany.'},
    ('DemandManager:Thermostats', 'Maximum_Heating_Setpoint_Reset'): {
        'by': 'Reset_Control', 'when': ('Fixed',), 'note': 'Used only when Reset_Control = Fixed.'},
    ('DemandManager:Thermostats', 'Maximum_Cooling_Setpoint_Reset'): {
        'by': 'Reset_Control', 'when': ('Fixed',), 'note': 'Used only when Reset_Control = Fixed.'},
    ('DemandManager:Ventilation', 'Fixed_Rate'): {
        'by': 'Limit_Control', 'when': ('FixedRate',), 'note': 'Used only when Limit_Control = FixedRate.'},
    ('DemandManager:Ventilation', 'Reduction_Ratio'): {
        'by': 'Limit_Control', 'when': ('ReductionRatio',), 'note': 'Used only when Limit_Control = ReductionRatio.'},

    # --- ExternalInterface ---
    ('ExternalInterface:Actuator', 'Initial_Value'): {
        'by': 'Initial_Value', 'when': ('<specified>',),
        'note': 'If a value is specified it is used during warm-up and sizing; if left blank the actuated component keeps its normal EnergyPlus-computed value until real time stepping starts.'},
}

METHOD_GROUPS = {
    ('ZoneControl:Thermostat', 'Control_Type_Schedule_Name'): {
        '0': None, '1': 'ThermostatSetpoint:SingleHeating', '2': 'ThermostatSetpoint:SingleCooling',
        '3': 'ThermostatSetpoint:SingleHeatingOrCooling', '4': 'ThermostatSetpoint:DualSetpoint',
        'note': 'Selects which Control <x> Object Type/Control <x> Name pair (up to 4 pairs) is active each timestep; 0 = Uncontrolled/floating (no thermostat object used).'},
    ('ZoneControl:Thermostat:OperativeTemperature', 'Radiative_Fraction_Input_Mode'): {
        'Constant': 'Fixed_Radiative_Fraction', 'Scheduled': 'Radiative_Fraction_Schedule_Name'},
    ('ZoneControl:Thermostat:TemperatureAndHumidity', 'Overcool_Range_Input_Method'): {
        'Constant': 'Overcool_Constant_Range', 'Scheduled': 'Overcool_Range_Schedule_Name'},
    ('ZoneControl:Thermostat:ThermalComfort', 'Thermal_Comfort_Control_Averaging_Method'): {
        'SpecificObject': 'Averaging_Method_Specific_Object_Name'},
    ('SetpointManager:OutdoorAirPretreat', 'Control_Variable'): {
        'Temperature': 'Minimum_Setpoint_Temperature/Maximum_Setpoint_Temperature',
        'MaximumTemperature': 'Minimum_Setpoint_Temperature/Maximum_Setpoint_Temperature',
        'MinimumTemperature': 'Minimum_Setpoint_Temperature/Maximum_Setpoint_Temperature',
        'HumidityRatio': 'Minimum_Setpoint_Humidity_Ratio/Maximum_Setpoint_Humidity_Ratio',
        'MaximumHumidityRatio': 'Minimum_Setpoint_Humidity_Ratio/Maximum_Setpoint_Humidity_Ratio',
        'MinimumHumidityRatio': 'Minimum_Setpoint_Humidity_Ratio/Maximum_Setpoint_Humidity_Ratio'},
    ('Controller:OutdoorAir', 'Economizer_Control_Type'): {
        'FixedDryBulb': 'Economizer_Maximum_Limit_DryBulb_Temperature',
        'FixedEnthalpy': 'Economizer_Maximum_Limit_Enthalpy',
        'FixedDewPointAndDryBulb': 'Economizer_Maximum_Limit_DryBulb_Temperature + Economizer_Maximum_Limit_Dewpoint_Temperature'},
    ('Controller:OutdoorAir', 'Minimum_Limit_Type'): {
        'FixedMinimum': 'flat minimum outdoor air flow', 'ProportionalMinimum': 'minimum scaled proportionally with current supply flow'},
    ('Controller:MechanicalVentilation', 'System_Outdoor_Air_Method'): {
        'ZoneSum': 'sum of zone outdoor air requirements',
        'Standard62.1VentilationRateProcedure': 'ASHRAE 62.1 VRP calculation using zone Design Specification Outdoor Air objects',
        'Standard62.1VentilationRateProcedureWithLimit': 'VRP capped at ZoneSum result',
        'IndoorAirQualityProcedure': 'IAQP; only Zone/ZoneList name fields used, Design Specification fields ignored',
        'ProportionalControlBasedOnOccupancySchedule': 'occupancy-schedule based proportional control',
        'ProportionalControlBasedOnDesignOccupancy': 'design-occupancy based proportional control',
        'ProportionalControlBasedOnDesignOARate': 'design-OA-rate based proportional control',
        'IndoorAirQualityProcedureGenericContaminant': 'IAQP for generic contaminant; only Zone/ZoneList name fields used'},
    ('AvailabilityManager:NightCycle', 'Control_Type'): {
        'StayOff': None, 'CycleOnAny': 'all zones monitored', 'CycleOnControlZone': 'Control_Zone_or_Zone_List_Name',
        'CycleOnAnyZoneFansOnly': 'zone fans only, no central fan', 'CycleOnAnyCoolingOrHeatingZone': 'Cooling_/Heating_Control_Zone_or_Zone_List_Name',
        'CycleOnAnyCoolingZone': 'Cooling_Control_Zone_or_Zone_List_Name', 'CycleOnAnyHeatingZone': 'Heating_Control_Zone_or_Zone_List_Name',
        'CycleOnAnyHeatingZoneFansOnly': 'Heating_Zone_Fans_Only_Zone_List_Name, no central fan'},
    ('AvailabilityManager:NightCycle', 'Cycling_Run_Time_Control_Type'): {
        'FixedRunTime': 'Cycling_Run_Time', 'Thermostat': 'runs until zone thermostat setpoint is met (Cycling_Run_Time ignored)',
        'ThermostatWithMinimumRunTime': 'runs at least Cycling_Run_Time then continues until setpoint is met'},
    ('AvailabilityManager:OptimumStart', 'Control_Type'): {
        'StayOff': None, 'ControlZone': 'Control_Zone_Name', 'MaximumofZoneList': 'Zone_List_Name (latest required start time across list governs)'},
    ('AvailabilityManager:OptimumStart', 'Control_Algorithm'): {
        'ConstantTemperatureGradient': 'Constant_Temperature_Gradient_during_Cooling/Heating',
        'AdaptiveTemperatureGradient': 'Initial_Temperature_Gradient_during_Cooling/Heating + Number_of_Previous_Days',
        'AdaptiveASHRAE': 'ASHRAE Handbook equations (default, no extra fields)',
        'ConstantStartTime': 'Constant_Start_Time'},
    ('AvailabilityManager:HybridVentilation', 'Ventilation_Control_Mode_Schedule_Name'): {
        '0': 'No control', '1': 'Temperature control (min/max outdoor temperature)', '2': 'Enthalpy control (min/max outdoor enthalpy)',
        '3': 'Dewpoint control (min/max outdoor dewpoint)', '4': 'Outdoor ventilation air control (ACH-based, AirflowNetwork only)',
        '5': 'Adaptive comfort 80% (requires People object with AdaptiveASH55)', '6': 'Adaptive comfort 90% (requires People object with AdaptiveASH55)',
        '7': 'CO2 control (requires ZoneControl:ContaminantController)'},
    ('DemandManager:ExteriorLights', 'Selection_Control'): {
        'All': 'limit all loads simultaneously', 'RotateOne': 'rotate limiting to a single load (uses Rotation_Duration)',
        'RotateMany': 'rotate, limiting all loads except one (uses Rotation_Duration)'},
    ('DemandManager:Ventilation', 'Limit_Control'): {'FixedRate': 'Fixed_Rate', 'ReductionRatio': 'Reduction_Ratio'},
}

AUTOSIZABLE = {
    ('Controller:WaterCoil', 'Controller_Convergence_Tolerance'),
    ('Controller:WaterCoil', 'Maximum_Actuated_Flow'),
    ('Controller:OutdoorAir', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('Controller:OutdoorAir', 'Maximum_Outdoor_Air_Flow_Rate'),
}

CONSTRAINTS = {
    'WindowShadingControl': [
        'Shading Type = ExteriorScreen may only be combined with Shading Control Type AlwaysOn, AlwaysOff, or OnIfScheduleAllows; no other Shading Control Type is valid for a screen.',
        'Shading Control Type = OnIfHighGlare requires Glare_Control_Is_Active = Yes and is only meaningful for windows in a daylit zone.',
        'Shading Control Type = MeetDaylightIlluminanceSetpoint is used only with Shading Type = SwitchableGlazing, in a zone with Daylighting:Controls.',
        'The four two-setpoint control types (OnIfHighOutdoorAirTempAndHighSolarOnWindow, OnIfHighOutdoorAirTempAndHighHorizontalSolar, OnIfHighZoneAirTempAndHighSolarOnWindow, OnIfHighZoneAirTempAndHighHorizontalSolar) require both Setpoint and Setpoint_2.',
        'BetweenGlassShade and BetweenGlassBlind are allowed only for double- and triple-pane constructions; for triple glazing the shading layer must sit between the two inner glass layers.',
        'Type_of_Slat_Angle_Control_for_Blinds only applies when Shading Type is InteriorBlind, ExteriorBlind or BetweenGlassBlind.',
        'When multiple WindowShadingControl objects reference the same window via a schedule, the Shading Type, Shading Control Type, setpoints and most other parameters must match across those objects; only the shading device/construction may differ.',
        'WindowShadingControl does not work with complex fenestration systems; a WindowShadingControl referencing a complex-fenestration surface is ignored by the program (only EMS can control those).',
        'IDD-per-field notes state that Construction_with_Shading_Name is required (with no Shading_Device_Material_Name alternative) when Shading Type = SwitchableGlazing, BetweenGlassShade, or BetweenGlassBlind.',
        'The EMS "Window Shading Control" actuator control type "Control Status" [ShadeStatus] accepts only these numeric values: -1.0 = No shading device, 0.0 = shading device off, 1.0 = interior shade on, 2.0 = glazing switched to darker state (SwitchableGlazing only), 3.0 = exterior shade on, 4.0 = exterior screen on, 6.0 = interior blind on, 7.0 = exterior blind on, 8.0 = between-glass shade on, 9.0 = between-glass blind on (5.0 is not a defined state). The value set must correspond to the Shading_Type actually declared on the target window\'s WindowShadingControl object (e.g. sending 6.0 to a window whose WindowShadingControl declares ExteriorBlind is a mismatch); documented failures of this kind manifest as fatal convergence errors mid-simulation, and a co-simulation (FMU/ExternalInterface) driving this actuator can report success even though the run died.',
        'The EMS Window Shading Control actuator is identified by the window (surface) name, not by the WindowShadingControl object name, because one WindowShadingControl can list several windows.',
        'A blind\'s companion "Slat Angle" actuator [degree] is only meaningful when the target window has a blind (InteriorBlind, ExteriorBlind, or BetweenGlassBlind); legal range is 0.0 to 180.0.',
    ],
    'ZoneControl:Thermostat': [
        'Only one Control <x> Object Type/Name pair may be specified per control type (SingleHeating, SingleCooling, SingleHeatingOrCooling, DualSetpoint) even though up to 4 pairs (Control 1-4) exist.',
        'Control_Type_Schedule_Name values outside 0-4 are not defined; a value with no matching Control <x> Object Type pair leaves the zone uncontrolled for that timestep.',
        'The heating and cooling setpoints of a DualSetpoint/StagedDualSetpoint control must be separated by at least twice the Temperature Difference Between Cutout And Setpoint or EnergyPlus issues a fatal error.',
    ],
    'ExternalInterface': [
        'ExternalInterface:Actuator "Actuated Component Unique Name" and "Actuated Component Type"/"Actuated Component Control Type" must exactly match an actuator listed in the EDD output file produced by an EMS-enabled run; the documentation does not describe range validation of the externally supplied value, so an out-of-range or type-mismatched value (e.g. a shading Control Status not valid for the target window) is not caught before being applied.',
        'ExternalInterface:Actuator / ExternalInterface:FunctionalMockupUnitExport:To:Actuator Initial Value, if left blank, means the actuated component keeps its EnergyPlus-computed value through warmup and sizing and is first overridden once real time stepping begins.',
    ],
    'AvailabilityManager': [
        'AvailabilityManager:DifferentialThermostat is always fully On or Off (never NoAction) and therefore must be the last manager listed in an AvailabilityManagerAssignmentList; any manager listed after it is never evaluated.',
        'For air loops and zone components, AvailabilityManagerAssignmentList precedence among simultaneous manager statuses is ForceOff > CycleOnZoneFansOnly > CycleOn > NoAction.',
        'For plant loops, the first availability manager in the list returning a status other than NoAction sets the loop status; later managers in the list are not consulted.',
        'AvailabilityManager:HybridVentilation cannot be listed inside an AvailabilityManagerAssignmentList; it is applied directly to an air loop or zone, one hybrid ventilation manager per zone (a zone-level manager is disabled if an air-loop-level one already governs that zone).',
        'AvailabilityManager:HybridVentilation mode 4 (Outdoor Ventilation Air Control) cannot be combined with ZoneVentilation/ZoneMixing objects on the same zone; modes 5-6 require a People object with Thermal_Comfort_Model_Type = AdaptiveASH55 in the controlled zone; mode 7 requires a ZoneControl:ContaminantController in the controlled zone.',
    ],
    'DemandManager': [
        'DemandManagerAssignmentList Demand_Manager_Priority = Sequential activates listed DemandManagers one at a time until demand drops below the limit; = All activates every manager in the list simultaneously.',
        'Limit_Step_Change is not yet implemented for any DemandManager:* object per the documentation.',
    ],
}

SECTIONS_READ = [
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-thermal-zone-description-geometry.html#windowpropertyshadingcontrol (WindowShadingControl)',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-zone-controls-thermostats.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-setpoint-managers.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-controllers.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-system-availability-managers.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-demand-limiting-controls.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-energy-management-system-ems.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-externalinterface.html',
    'https://bigladdersoftware.com/epx/docs/9-6/ems-application-guide/thermal-envelope.html (Window Shading Control EMS actuator Control Status values - not documented in the Input Output Reference EMS group page, only in the Application Guide for EMS)',
]

IDD_DISAGREEMENTS = [
    'FenestrationSurface:Detailed Surface Type: the WindowShadingControl prose (Input Output Reference) and its own memo refer to "GlazedDoor" as a valid target surface class, but Energy+.idd A2 "Surface Type" key list for FenestrationSurface:Detailed is InteriorShade-unrelated and actually spells the key GlassDoor (Window, Door, GlassDoor, TubularDaylightDome, TubularDaylightDiffuser). There is no "GlazedDoor" key in the IDD; "GlazedDoor" is legacy/simplified-object naming (the GlazedDoor simple object) rather than the FenestrationSurface:Detailed choice key.',
    'The Input Output Reference EMS group page (group-energy-management-system-ems.html) does not itself document the "Window Shading Control" actuator or its Control Status numeric codes; that table only appears in the separate Application Guide for EMS (thermal-envelope.html). Treated here as a documentation-location gap rather than a content conflict.',
]
