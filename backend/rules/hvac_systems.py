"""Rules from: HVAC: Primary and Secondary Systems; Group - Node-Branch Management;
Group - Zone Equipment; Group - Zone HVAC Air Loop Terminal Units;
Group - Zone Forced Air Units; Group - Air Distribution; Group - Air Path.
(EnergyPlus 9.6 Input Output Reference, bigladdersoftware.com/epx/docs/9-6/input-output-reference/)

All class and field names verified against C:/EnergyPlusV9-6-0/Energy+.idd.
"""

GATED = {
    # --- AirTerminal:SingleDuct:VAV:Reheat / VAV:NoReheat ---
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Constant_Minimum_Air_Flow_Fraction'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Constant',),
        'note': 'Also usable (optional) for sizing when method is Scheduled.'},
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Fixed_Minimum_Air_Flow_Rate'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('FixedFlowRate',),
        'note': 'Also usable (optional) for sizing when method is Scheduled.'},
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Minimum_Air_Flow_Fraction_Schedule_Name'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Scheduled',), 'note': 'Fraction schedule 0-1.'},
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Flow_per_Zone_Floor_Area_During_Reheat'): {
        'by': 'Damper_Heating_Action', 'when': ('ReverseWithLimits',),
        'note': 'Also requires Reheat_Coil_Object_Type = Coil:Heating:Water.'},
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Flow_Fraction_During_Reheat'): {
        'by': 'Damper_Heating_Action', 'when': ('ReverseWithLimits',),
        'note': 'Also requires Reheat_Coil_Object_Type = Coil:Heating:Water.'},
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'): {
        'by': 'Reheat_Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Heating:Steam'),
        'note': 'Not used for gas or electric reheat coils.'},
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Constant_Minimum_Air_Flow_Fraction'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Constant',), 'note': 'Fraction of Maximum Air Flow Rate.'},
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Fixed_Minimum_Air_Flow_Rate'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('FixedFlowRate',), 'note': 'Fixed volume flow rate.'},
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Minimum_Air_Flow_Fraction_Schedule_Name'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Scheduled',), 'note': 'Fraction schedule 0-1.'},
    # --- Reheat/heating coils gated by coil type across terminal units ---
    ('AirTerminal:SingleDuct:ConstantVolume:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'): {
        'by': 'Reheat_Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Heating:Steam'),
        'note': 'Not used when reheat coil is gas or electric.'},
    ('AirTerminal:SingleDuct:SeriesPIU:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'): {
        'by': 'Reheat_Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Heating:Steam'),
        'note': 'Not used when reheat coil is gas or electric.'},
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'): {
        'by': 'Reheat_Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Heating:Steam'),
        'note': 'Not used when reheat coil is gas or electric.'},
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeInduction', 'Maximum_Hot_Water_Flow_Rate'): {
        'by': 'Heating_Coil_Object_Type', 'when': ('Coil:Heating:Water',),
        'note': 'Not used when heating coil type is gas or electric (only Coil:Heating:Water is valid here).'},
    ('ZoneHVAC:UnitHeater', 'Maximum_Hot_Water_or_Steam_Flow_Rate'): {
        'by': 'Heating_Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Heating:Steam'),
        'note': 'Not used when heating coil is gas or electric.'},
    # --- Design Specification ZoneHVAC Sizing scalable-sizing fields (generic pattern) ---
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate'): {
        'by': 'Cooling_Supply_Air_Flow_Rate_Method', 'when': ('SupplyAirFlowRate',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate_Per_Floor_Area'): {
        'by': 'Cooling_Supply_Air_Flow_Rate_Method', 'when': ('FlowPerFloorArea',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate'): {
        'by': 'Cooling_Supply_Air_Flow_Rate_Method', 'when': ('FractionOfAutosizedCoolingAirflow',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate_Per_Unit_Cooling_Capacity'): {
        'by': 'Cooling_Supply_Air_Flow_Rate_Method', 'when': ('FlowPerCoolingCapacity',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate'): {
        'by': 'Heating_Supply_Air_Flow_Rate_Method', 'when': ('SupplyAirFlowRate',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate_Per_Floor_Area'): {
        'by': 'Heating_Supply_Air_Flow_Rate_Method', 'when': ('FlowPerFloorArea',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Fraction_of_Heating_Supply_Air_Flow_Rate'): {
        'by': 'Heating_Supply_Air_Flow_Rate_Method', 'when': ('FractionOfAutosizedHeatingAirflow',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate_Per_Unit_Heating_Capacity'): {
        'by': 'Heating_Supply_Air_Flow_Rate_Method', 'when': ('FlowPerHeatingCapacity',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate'): {
        'by': 'No_Load_Supply_Air_Flow_Rate_Method', 'when': ('SupplyAirFlowRate',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate_Per_Floor_Area'): {
        'by': 'No_Load_Supply_Air_Flow_Rate_Method', 'when': ('FlowPerFloorArea',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Fraction_of_Cooling_Supply_Air_Flow_Rate'): {
        'by': 'No_Load_Supply_Air_Flow_Rate_Method', 'when': ('FractionOfAutosizedCoolingAirflow',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Fraction_of_Heating_Supply_Air_Flow_Rate'): {
        'by': 'No_Load_Supply_Air_Flow_Rate_Method', 'when': ('FractionOfAutosizedHeatingAirflow',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('CoolingDesignCapacity',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity_Per_Floor_Area'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Fraction_of_Autosized_Cooling_Design_Capacity'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('FractionOfAutosizedCoolingCapacity',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('HeatingDesignCapacity',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': 'Required field for this method.'},
    # --- Same Heating Design Capacity Method pattern repeated on baseboard/radiant classes ---
    ('ZoneHVAC:Baseboard:Convective:Water', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    ('ZoneHVAC:Baseboard:Convective:Water', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': 'Required field for this method.'},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Cooling_Design_Capacity_Per_Floor_Area'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    ('ZoneHVAC:HighTemperatureRadiant', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': 'Required field for this method.'},
    # --- ZoneHVAC:IdealLoadsAirSystem ---
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Heating_Air_Flow_Rate'): {
        'by': 'Heating_Limit', 'when': ('LimitFlowRate', 'LimitFlowRateAndCapacity'), 'note': 'Ignored if Heating Limit = NoLimit.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Sensible_Heating_Capacity'): {
        'by': 'Heating_Limit', 'when': ('LimitCapacity', 'LimitFlowRateAndCapacity'), 'note': 'Ignored if Heating Limit = NoLimit.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Cooling_Air_Flow_Rate'): {
        'by': 'Cooling_Limit', 'when': ('LimitFlowRate', 'LimitFlowRateAndCapacity'),
        'note': 'Ignored if Cooling Limit = NoLimit; also required if Outdoor Air Economizer Type != NoEconomizer.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Total_Cooling_Capacity'): {
        'by': 'Cooling_Limit', 'when': ('LimitCapacity', 'LimitFlowRateAndCapacity'), 'note': 'Ignored if Cooling Limit = NoLimit.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Cooling_Sensible_Heat_Ratio'): {
        'by': 'Dehumidification_Control_Type', 'when': ('ConstantSensibleHeatRatio',), 'note': 'Only used with this dehumidification mode.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Latent_Heat_Recovery_Effectiveness'): {
        'by': 'Heat_Recovery_Type', 'when': ('Enthalpy',), 'note': 'Applicable only if Heat Recovery Type is Enthalpy.'},
    ('ZoneHVAC:IdealLoadsAirSystem', 'Outdoor_Air_Inlet_Node_Name'): {
        'by': 'Design_Specification_Outdoor_Air_Object_Name', 'when': ('<any non-blank>',),
        'note': 'If Design Specification Outdoor Air Object Name is blank there is no outdoor air and remaining OA fields are ignored.'},
    # --- ZoneHVAC:FourPipeFanCoil ---
    ('ZoneHVAC:FourPipeFanCoil', 'Low_Speed_Supply_Air_Flow_Ratio'): {
        'by': 'Capacity_Control_Method', 'when': ('CyclingFan', 'ASHRAE90VariableFan'), 'note': 'Leave blank for other capacity control methods.'},
    ('ZoneHVAC:FourPipeFanCoil', 'Medium_Speed_Supply_Air_Flow_Ratio'): {
        'by': 'Capacity_Control_Method', 'when': ('CyclingFan', 'MultiSpeedFan'), 'note': 'Leave blank for other capacity control methods.'},
    ('ZoneHVAC:FourPipeFanCoil', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('ASHRAE90VariableFan',),
        'note': 'Leave blank/0 to control to zone load per ASHRAE 90.1 (requires zone sizing run).'},
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('ASHRAE90VariableFan',),
        'note': 'Leave blank/0 to control to zone load per ASHRAE 90.1 (requires zone sizing run).'},
    # --- ZoneHVAC:PackagedTerminalAirConditioner / PackagedTerminalHeatPump ---
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('SingleZoneVAV',), 'note': 'Only used with SingleZoneVAV.'},
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('SingleZoneVAV',), 'note': 'Only used with SingleZoneVAV.'},
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('SingleZoneVAV',), 'note': 'Only used with SingleZoneVAV.'},
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'): {
        'by': 'Capacity_Control_Method', 'when': ('SingleZoneVAV',), 'note': 'Only used with SingleZoneVAV.'},
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'No_Load_Supply_Air_Flow_Rate'): {
        'by': 'Supply_Air_Fan_Operating_Mode_Schedule_Name', 'when': ('<continuous fan: values > 0>',),
        'note': 'Only used when the fan operating mode schedule specifies continuous fan operation.'},
    ('ZoneHVAC:PackagedTerminalHeatPump', 'No_Load_Supply_Air_Flow_Rate'): {
        'by': 'Supply_Air_Fan_Operating_Mode_Schedule_Name', 'when': ('<continuous fan: values > 0>',),
        'note': 'Only used when heat pump fan operating mode is continuous.'},
    # --- ZoneHVAC:UnitVentilator / VentilatedSlab outdoor air control ---
    ('ZoneHVAC:UnitVentilator', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'): {
        'by': 'Outdoor_Air_Control_Type', 'when': ('VariablePercent', 'FixedTemperature'),
        'note': 'Schedule values interpreted as fraction (VariablePercent) or temperature (FixedTemperature); ignored for FixedAmount.'},
    ('ZoneHVAC:VentilatedSlab', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'): {
        'by': 'Outdoor_Air_Control_Type', 'when': ('VariablePercent', 'FixedTemperature'),
        'note': 'Schedule values interpreted as fraction or temperature depending on control type.'},
    # --- AirTerminal:DualDuct:VAV:OutdoorAir ---
    ('AirTerminal:DualDuct:VAV:OutdoorAir', 'Per_Person_Ventilation_Rate_Mode'): {
        'by': 'Design_Specification_Outdoor_Air_Object_Name', 'when': ('<any non-blank, with Outdoor Air Flow per Person > 0>',),
        'note': 'Only meaningful once a DesignSpecification:OutdoorAir object with a per-person rate is referenced.'},
    ('AirTerminal:SingleDuct:Mixer', 'Per_Person_Ventilation_Rate_Mode'): {
        'by': 'Design_Specification_Outdoor_Air_Object_Name', 'when': ('<any non-blank, with Outdoor Air Flow per Person > 0>',),
        'note': 'Demand-controlled ventilation mode only matters when a per-person OA rate is in effect.'},
}

METHOD_GROUPS = {
    # Generic scalable-sizing object referenced by almost all ZoneHVAC:* equipment via
    # "Design Specification ZoneHVAC Sizing Object Name" -- the single richest source of
    # the six priority method fields.
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Cooling_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Cooling_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingAirflow': 'Cooling_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FlowPerCoolingCapacity': 'Cooling_Supply_Air_Flow_Rate_Per_Unit_Cooling_Capacity',
    },
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Heating_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Heating_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedHeatingAirflow': 'Heating_Fraction_of_Heating_Supply_Air_Flow_Rate',
        'FlowPerHeatingCapacity': 'Heating_Supply_Air_Flow_Rate_Per_Unit_Heating_Capacity',
    },
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'No_Load_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'No_Load_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingAirflow': 'No_Load_Fraction_of_Cooling_Supply_Air_Flow_Rate',
        'FractionOfAutosizedHeatingAirflow': 'No_Load_Fraction_of_Heating_Supply_Air_Flow_Rate',
    },
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity_Method'): {
        'None': None,
        'CoolingDesignCapacity': 'Cooling_Design_Capacity',
        'CapacityPerFloorArea': 'Cooling_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedCoolingCapacity': 'Fraction_of_Autosized_Cooling_Design_Capacity',
    },
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity_Method'): {
        'None': None,
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    # Same Heating/Cooling Design Capacity Method pattern, defined locally (no DesignSpec object) on:
    ('ZoneHVAC:Baseboard:RadiantConvective:Water:Design', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:Baseboard:Convective:Water', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:Baseboard:Convective:Electric', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Cooling_Design_Capacity_Method'): {
        'None': None,
        'CoolingDesignCapacity': 'Cooling_Design_Capacity',
        'CapacityPerFloorArea': 'Cooling_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedCoolingCapacity': 'Fraction_of_Autosized_Cooling_Design_Capacity',
    },
    ('ZoneHVAC:LowTemperatureRadiant:Electric', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:HighTemperatureRadiant', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Design_Capacity_Method'): {
        'None': None,
        'CoolingDesignCapacity': 'Cooling_Design_Capacity',
        'CapacityPerFloorArea': 'Cooling_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedCoolingCapacity': 'Fraction_of_Autosized_Cooling_Design_Capacity',
    },
    # Zone Minimum Air Flow Input Method (VAV terminal units) -- exact IDD field name,
    # NOT "Zone Minimum Air Flow Method" as sometimes written in prose.
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Zone_Minimum_Air_Flow_Input_Method'): {
        'Constant': 'Constant_Minimum_Air_Flow_Fraction',
        'FixedFlowRate': 'Fixed_Minimum_Air_Flow_Rate',
        'Scheduled': 'Minimum_Air_Flow_Fraction_Schedule_Name',
    },
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Zone_Minimum_Air_Flow_Input_Method'): {
        'Constant': 'Constant_Minimum_Air_Flow_Fraction',
        'FixedFlowRate': 'Fixed_Minimum_Air_Flow_Rate',
        'Scheduled': 'Minimum_Air_Flow_Fraction_Schedule_Name',
    },
    # ZoneHVAC:IdealLoadsAirSystem Heating/Cooling Limit -- not literally named "*Method"
    # but function identically (key selects which capacity/flow-rate sibling field is used).
    ('ZoneHVAC:IdealLoadsAirSystem', 'Heating_Limit'): {
        'NoLimit': None,
        'LimitFlowRate': 'Maximum_Heating_Air_Flow_Rate',
        'LimitCapacity': 'Maximum_Sensible_Heating_Capacity',
        'LimitFlowRateAndCapacity': ('Maximum_Heating_Air_Flow_Rate', 'Maximum_Sensible_Heating_Capacity'),
    },
    ('ZoneHVAC:IdealLoadsAirSystem', 'Cooling_Limit'): {
        'NoLimit': None,
        'LimitFlowRate': 'Maximum_Cooling_Air_Flow_Rate',
        'LimitCapacity': 'Maximum_Total_Cooling_Capacity',
        'LimitFlowRateAndCapacity': ('Maximum_Cooling_Air_Flow_Rate', 'Maximum_Total_Cooling_Capacity'),
    },
    # ZoneHVAC:UnitVentilator / VentilatedSlab Outdoor Air Control Type
    ('ZoneHVAC:UnitVentilator', 'Outdoor_Air_Control_Type'): {
        'FixedAmount': 'Minimum_Outdoor_Air_Flow_Rate',
        'VariablePercent': ('Minimum_Outdoor_Air_Schedule_Name', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'),
        'FixedTemperature': ('Minimum_Outdoor_Air_Schedule_Name', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'),
    },
    ('ZoneHVAC:VentilatedSlab', 'Outdoor_Air_Control_Type'): {
        'FixedAmount': 'Minimum_Outdoor_Air_Flow_Rate',
        'VariablePercent': ('Minimum_Outdoor_Air_Schedule_Name', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'),
        'FixedTemperature': ('Minimum_Outdoor_Air_Schedule_Name', 'Maximum_Outdoor_Air_Fraction_or_Temperature_Schedule_Name'),
    },
    # ZoneHVAC:EquipmentList Load Distribution Scheme
    ('ZoneHVAC:EquipmentList', 'Load_Distribution_Scheme'): {
        'SequentialLoad': ('Zone_Equipment_1_Sequential_Cooling_Fraction_Schedule_Name',
                            'Zone_Equipment_1_Sequential_Heating_Fraction_Schedule_Name'),
        'UniformLoad': None,
        'UniformPLR': None,
        'SequentialUniformPLR': None,
    },
    # Fan coil capacity control method
    ('ZoneHVAC:FourPipeFanCoil', 'Capacity_Control_Method'): {
        'ConstantFanVariableFlow': None,
        'CyclingFan': ('Low_Speed_Supply_Air_Flow_Ratio', 'Medium_Speed_Supply_Air_Flow_Ratio'),
        'VariableFanVariableFlow': None,
        'VariableFanConstantFlow': None,
        'MultiSpeedFan': 'Medium_Speed_Supply_Air_Flow_Ratio',
        'ASHRAE90VariableFan': ('Minimum_Supply_Air_Temperature_in_Cooling_Mode', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    },
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Capacity_Control_Method'): {
        'None': None,
        'SingleZoneVAV': ('Minimum_Supply_Air_Temperature_in_Cooling_Mode', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    },
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Capacity_Control_Method'): {
        'None': None,
        'SingleZoneVAV': ('Minimum_Supply_Air_Temperature_in_Cooling_Mode', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    },
    # AirTerminal:SingleDuct:VAV:Reheat Damper Heating Action
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Damper_Heating_Action'): {
        'Normal': None,
        'Reverse': None,
        'ReverseWithLimits': ('Maximum_Flow_per_Zone_Floor_Area_During_Reheat', 'Maximum_Flow_Fraction_During_Reheat'),
    },
}

AUTOSIZABLE = {
    # AirTerminal single-duct / dual-duct terminal units
    ('AirTerminal:SingleDuct:ConstantVolume:Reheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:NoReheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Constant_Minimum_Air_Flow_Fraction'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Fixed_Minimum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Flow_per_Zone_Floor_Area_During_Reheat'),
    ('AirTerminal:SingleDuct:VAV:Reheat', 'Maximum_Flow_Fraction_During_Reheat'),
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Constant_Minimum_Air_Flow_Fraction'),
    ('AirTerminal:SingleDuct:VAV:NoReheat', 'Fixed_Minimum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat:VariableSpeedFan', 'Maximum_Cooling_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat:VariableSpeedFan', 'Maximum_Heating_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:Reheat:VariableSpeedFan', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:HeatAndCool:Reheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:HeatAndCool:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:VAV:HeatAndCool:NoReheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:SeriesPIU:Reheat', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:SeriesPIU:Reheat', 'Maximum_Primary_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:SeriesPIU:Reheat', 'Minimum_Primary_Air_Flow_Fraction'),
    ('AirTerminal:SingleDuct:SeriesPIU:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Maximum_Primary_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Maximum_Secondary_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Minimum_Primary_Air_Flow_Fraction'),
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Fan_On_Flow_Fraction'),
    ('AirTerminal:SingleDuct:ParallelPIU:Reheat', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeInduction', 'Maximum_Total_Air_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeInduction', 'Maximum_Hot_Water_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeInduction', 'Maximum_Cold_Water_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeBeam', 'Design_Primary_Air_Volume_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeBeam', 'Design_Chilled_Water_Volume_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeBeam', 'Design_Hot_Water_Volume_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:FourPipeBeam', 'Zone_Total_Beam_Length'),
    ('AirTerminal:SingleDuct:ConstantVolume:CooledBeam', 'Supply_Air_Volumetric_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:CooledBeam', 'Maximum_Total_Chilled_Water_Volumetric_Flow_Rate'),
    ('AirTerminal:SingleDuct:ConstantVolume:CooledBeam', 'Number_of_Beams'),
    ('AirTerminal:SingleDuct:ConstantVolume:CooledBeam', 'Beam_Length'),
    ('AirTerminal:SingleDuct:ConstantVolume:CooledBeam', 'Coefficient_of_Induction_Kin'),
    ('AirTerminal:DualDuct:ConstantVolume', 'Maximum_Air_Flow_Rate'),
    ('AirTerminal:DualDuct:VAV', 'Maximum_Damper_Air_Flow_Rate'),
    ('AirTerminal:DualDuct:VAV:OutdoorAir', 'Maximum_Terminal_Air_Flow_Rate'),

    # ZoneHVAC forced-air units
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Cold_Water_Flow_Rate'),
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Hot_Water_Flow_Rate'),
    ('ZoneHVAC:FourPipeFanCoil', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'),
    ('ZoneHVAC:FourPipeFanCoil', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Cooling_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Heating_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'No_Load_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Cooling_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Heating_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'No_Load_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'),
    ('ZoneHVAC:PackagedTerminalAirConditioner', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Cooling_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Heating_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'No_Load_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Cooling_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Heating_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'No_Load_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Minimum_Supply_Air_Temperature_in_Cooling_Mode'),
    ('ZoneHVAC:PackagedTerminalHeatPump', 'Maximum_Supply_Air_Temperature_in_Heating_Mode'),
    ('ZoneHVAC:WaterToAirHeatPump', 'Cooling_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'Heating_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'No_Load_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'Cooling_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'Heating_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'No_Load_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:WaterToAirHeatPump', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('ZoneHVAC:UnitVentilator', 'Maximum_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Maximum_Hot_Water_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Minimum_Hot_Water_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Maximum_Cold_Water_Flow_Rate'),
    ('ZoneHVAC:UnitVentilator', 'Minimum_Cold_Water_Flow_Rate'),
    ('ZoneHVAC:UnitHeater', 'Maximum_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:UnitHeater', 'Maximum_Hot_Water_or_Steam_Flow_Rate'),
    ('ZoneHVAC:EvaporativeCoolerUnit', 'Design_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'Cooling_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'No_Cooling_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'Heating_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'No_Heating_Supply_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'Cooling_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'Heating_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'No_Load_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:TerminalUnit:VariableRefrigerantFlow', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Heating_Air_Flow_Rate'),
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Sensible_Heating_Capacity'),
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Cooling_Air_Flow_Rate'),
    ('ZoneHVAC:IdealLoadsAirSystem', 'Maximum_Total_Cooling_Capacity'),
    ('ZoneHVAC:VentilatedSlab', 'Maximum_Air_Flow_Rate'),
    ('ZoneHVAC:VentilatedSlab', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:VentilatedSlab', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:HighTemperatureRadiant', 'Heating_Design_Capacity'),

    # Baseboard / radiant / cooling panel scalable-sizing capacities
    ('ZoneHVAC:Baseboard:Convective:Water', 'Heating_Design_Capacity'),
    ('ZoneHVAC:Baseboard:Convective:Water', 'U_Factor_Times_Area_Value'),
    ('ZoneHVAC:Baseboard:Convective:Water', 'Maximum_Water_Flow_Rate'),
    ('ZoneHVAC:LowTemperatureRadiant:Electric', 'Heating_Design_Capacity'),
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Design_Capacity'),
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Maximum_Chilled_Water_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity'),

    # Air Distribution / main air loop
    ('AirLoopHVAC', 'Design_Supply_Air_Flow_Rate'),
}

CONSTRAINTS = {
    'AirTerminal:SingleDuct:VAV:Reheat': [
        'Only one of Constant Minimum Air Flow Fraction and Fixed Minimum Air Flow Rate should be given a value; if both are entered the larger resulting flow is used for sizing.',
        'Maximum Flow per Zone Floor Area During Reheat and Maximum Flow Fraction During Reheat only apply when Reheat Coil Object Type = Coil:Heating:Water and Damper Heating Action = ReverseWithLimits; the reheat flow never exceeds Maximum Air Flow Rate.',
        'If Design Specification Outdoor Air Object Name is entered, supply air flow may be increased above the minimum to meet the outdoor air requirement, but never exceeds Maximum Air Flow Rate.',
    ],
    'AirTerminal:SingleDuct:VAV:NoReheat': [
        'No reheat coil is included; heating (if any) must come from baseboard or other zone equipment.',
        'If Design Specification Outdoor Air Object Name is blank, the terminal unit is not controlled for outdoor air.',
    ],
    'AirTerminal:SingleDuct:ConstantVolume:Reheat': [
        'Reheat Coil Object Type must be one of Coil:Heating:Water, Coil:Heating:Electric, Coil:Heating:Fuel, or Coil:Heating:Steam.',
    ],
    'AirTerminal:SingleDuct:SeriesPIU:Reheat': [
        'Fan is downstream of the primary and secondary air inlets (blow-through); valid fan types are Fan:SystemModel or Fan:ConstantVolume.',
        'Total (constant) unit air flow rate is fixed; the primary air damper varies the primary/secondary mixing to meet load.',
    ],
    'AirTerminal:SingleDuct:ParallelPIU:Reheat': [
        'Secondary fan sits in the secondary air stream and runs intermittently based on Fan On Flow Fraction, Availability Schedule, and availability managers.',
        'Maximum Secondary Air Flow Rate is typically less than Maximum Primary Air Flow Rate.',
    ],
    'AirTerminal:SingleDuct:ConstantVolume:FourPipeBeam': [
        'Omitting both chilled-water node fields models a heating-only (two-pipe) beam; omitting both hot-water node fields models a cooling-only beam.',
        'The three capacity-modification-factor curve names (temperature difference, air flow, water flow) are required whenever the beam is connected to the corresponding (chilled or hot) water plant.',
    ],
    'AirTerminal:SingleDuct:Mixer': [
        'ZoneHVAC Unit Object Type is restricted to a fixed list of terminal-compatible equipment (e.g. ZoneHVAC:FourPipeFanCoil, ZoneHVAC:PackagedTerminalAirConditioner/HeatPump, ZoneHVAC:WaterToAirHeatPump, ZoneHVAC:UnitVentilator, ZoneHVAC:TerminalUnit:VariableRefrigerantFlow, AirLoopHVAC:UnitarySystem).',
        'Mixer Connection Type (InletSide vs SupplySide) determines which node of the ZoneHVAC equipment the mixer outlet feeds.',
    ],
    'ZoneHVAC:AirDistributionUnit': [
        'Air Terminal Object Type is restricted to the fixed set of AirTerminal:* classes defined in the IDD (dual-duct, single-duct reheat/no-reheat/VAV/PIU/beam/induction/mixer/user-defined variants).',
    ],
    'ZoneHVAC:EquipmentList': [
        'Sequential Cooling/Heating Fraction Schedule Name fields for each equipment slot are only meaningful when Load Distribution Scheme = SequentialLoad; otherwise ignored.',
        'Zone Equipment <x> Object Type is restricted to a fixed list of ZoneHVAC:*, Fan:ZoneExhaust, WaterHeater:HeatPump:*, HeatExchanger:AirToAir:FlatPlate, and AirLoopHVAC:UnitarySystem.',
    ],
    'ZoneHVAC:EquipmentConnections': [
        'Every zone with HVAC equipment needs a return air node, even if not connected to anything.',
        'If Zone Return Air Node 1 Flow Rate Basis Node or NodeList Name is blank, the base return air flow rate is the total supply inlet flow minus the total exhaust flow for the zone.',
    ],
    'ZoneHVAC:IdealLoadsAirSystem': [
        'If Design Specification Outdoor Air Object Name is blank, there is no outdoor air and the outdoor-air-related fields (economizer, heat recovery, demand-controlled ventilation) are ignored.',
        'Maximum Cooling Air Flow Rate is required whenever Outdoor Air Economizer Type is anything other than NoEconomizer.',
        'System Inlet Air Node Name is only required when connected to an AirLoopHVAC:ReturnPlenum.',
    ],
    'ZoneHVAC:FourPipeFanCoil': [
        'Required fan object type depends on Capacity Control Method (e.g. CyclingFan needs Fan:OnOff or Fan:SystemModel; VariableFanVariableFlow/VariableFanConstantFlow need Fan:VariableVolume or Fan:SystemModel).',
        'Outdoor Air Mixer Object Type/Name and Maximum Outdoor Air Flow Rate should be left blank/zero when the fan coil is fed by a central dedicated outdoor air system through an AirTerminal:SingleDuct:Mixer.',
    ],
    'ZoneHVAC:PackagedTerminalAirConditioner': [
        'Cooling/Heating/No Load Outdoor Air Flow Rate are forced to zero when the unit is connected to central dedicated outdoor air via AirTerminal:SingleDuct:Mixer.',
        'Fan:ConstantVolume is only valid for Supply Air Fan Object Type when continuous fan operation is used for the entire simulation.',
    ],
    'ZoneHVAC:PackagedTerminalHeatPump': [
        'Cooling/Heating/No Load Outdoor Air Flow Rate are forced to zero when the unit is connected to central dedicated outdoor air via AirTerminal:SingleDuct:Mixer.',
        'Heating Coil Object Type must be a DX heating coil (Coil:Heating:DX:SingleSpeed or VariableSpeed); Cooling Coil Object Type must be a matching DX cooling coil.',
    ],
    'ZoneHVAC:TerminalUnit:VariableRefrigerantFlow': [
        'Supply Air Fan Object Type and the Cooling/Heating Coil Object Type must match the VRF outdoor unit model in use (AirConditioner:VariableRefrigerantFlow vs the FluidTemperatureControl variants require different fan and coil types).',
        'Several fields (fan placement/type, availability schedule) are required for zone-equipment use but must be left blank when the terminal unit is used inside an AirLoopHVAC:OutdoorAirSystem:EquipmentList or on a main AirLoopHVAC branch with no fan.',
    ],
    'DesignSpecification:ZoneHVAC:Sizing': [
        'Each *Method field defaults its dependent fields to blank/zero if the relevant coil (cooling or heating) is not present in the referencing ZoneHVAC equipment.',
        'This single object supplies scalable sizing for essentially all ZoneHVAC:* equipment via their "Design Specification ZoneHVAC Sizing Object Name" field.',
    ],
    'AirLoopHVAC:SupplyPath': [
        'Supply path components must be listed in flow order and each Component <x> Object Type must be AirLoopHVAC:ZoneSplitter or AirLoopHVAC:SupplyPlenum.',
    ],
    'AirLoopHVAC:ReturnPath': [
        'Return path components must be listed in flow order and each Component <x> Object Type must be AirLoopHVAC:ZoneMixer or AirLoopHVAC:ReturnPlenum.',
    ],
    'Branch': [
        'The outlet node of component N must have the same node name as the inlet node of component N+1 on the branch.',
    ],
    'BranchList': [
        'Branches in a BranchList must be listed in flow order: inlet branch, then parallel branches, then outlet branch.',
    ],
    'ConnectorList': [
        'A maximum of one mixer and one splitter is allowed for each loop segment referenced by a ConnectorList.',
    ],
    'NodeList': [
        'Each NodeList is limited to a maximum of 25 nodes; use multiple NodeLists if more are needed.',
    ],
    'Pipe:Indoor': [
        'Ambient Temperature Zone Name is used only when Environment Type = Zone.',
        'Ambient Temperature Schedule Name and Ambient Air Velocity Schedule Name are used only when Environment Type = Schedule.',
    ],
}

SECTIONS_READ = [
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/hvac-primary-and-secondary-systems.html (overview only; no per-field content on this page)',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-node-branch-management.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-zone-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-air-distribution-equipment.html (Group - Zone HVAC Air Loop Terminal Units)',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-zone-forced-air-units.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-air-distribution.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-air-path.html (content overlaps group-air-distribution.html; AirLoopHVAC:SupplyPath/ReturnPath covered there)',
    'C:/EnergyPlusV9-6-0/Energy+.idd (authoritative source for all field names, \\autosizable markers, \\key choices, and \\note gating text; prose from the HTML pages was cross-checked against it and the IDD spelling/field-name wins on any disagreement)',
]

IDD_DISAGREEMENTS = [
    "AirTerminal:SingleDuct:VAV:Reheat / VAV:NoReheat: the IDD field is 'Zone Minimum Air Flow Input Method', not 'Zone Minimum Air Flow Method' as an initial web summary of the page rendered it.",
    "ZoneHVAC:UnitVentilator / ZoneHVAC:VentilatedSlab: the IDD choice field is 'Outdoor Air Control Type' (keys FixedAmount/VariablePercent/FixedTemperature); an initial web summary paraphrased it as separate concepts without the exact field name.",
    "ZoneHVAC:IdealLoadsAirSystem 'Heating Limit' / 'Cooling Limit' are plain \\key choice fields functioning like a *Method field, but are not literally named '*Method' in the IDD.",
]
