"""Rules from: Group - Non-Zone Equipment, Group - Electric Load Center-Generator
Specifications, Group - Operational Faults, Group - Performance Curves,
Group Performance Tables, Group Fluid Properties, Group - Hybrid Model,
Group User Defined HVAC and Plant Component Models, Group - Python Plugins/
Python EMS, HVAC Template Objects.
EnergyPlus 9.6 Input Output Reference (https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/)
Field names, keys, defaults and autosizable markers verified directly against
C:/EnergyPlusV9-6-0/Energy+.idd (parsed programmatically); prose disagreements
are listed in IDD_DISAGREEMENTS below.

Notes on section coverage:
- Group - Non-Zone Equipment contains exactly one object in this IDD version
  (LoadProfile:Plant) -- confirmed against the IDD's own "\\group Non-Zone
  Equipment" tag. It has no GATED, METHOD_GROUPS or AUTOSIZABLE fields.
- Group - Performance Curves and Group Performance Tables have no GATED,
  METHOD_GROUPS (curve/table TYPE selection itself is the "method" -- there
  is no in-object branching field) or AUTOSIZABLE fields; their only rules
  are the independent-variable/output clamping CONSTRAINTS.
- Group - Python Plugins/Python EMS has no GATED, METHOD_GROUPS or
  AUTOSIZABLE fields; its rules are all cross-object reference CONSTRAINTS.
- HVAC Template Objects is a large group (~30 HVACTemplate:Zone/System/Plant
  objects). Coverage here is representative of the recurring, explicitly
  documented gating patterns (Outdoor Air Method, Zone Minimum Air Flow
  Input Method, Zone Cooling/Heating Design Supply Air Temperature Input
  Method, Heating/Cooling Limit, Condenser Type, Chiller Type, Defrost
  Control) plus a full sweep of every \\autosizable field found in the
  group, rather than an exhaustive field-by-field listing of all ~30 objects.
"""

GATED = {
    # --- Electric Load Center / Generators ---
    ('ElectricLoadCenter:Transformer', 'Rated_No_Load_Loss'): {
        'by': 'Performance_Input_Method', 'when': ('RatedLosses',),
        'note': 'Only required when Performance Input Method = RatedLosses.'},
    ('ElectricLoadCenter:Transformer', 'Rated_Load_Loss'): {
        'by': 'Performance_Input_Method', 'when': ('RatedLosses',),
        'note': 'Only required when Performance Input Method = RatedLosses.'},
    ('ElectricLoadCenter:Transformer', 'Nameplate_Efficiency'): {
        'by': 'Performance_Input_Method', 'when': ('NominalEfficiency',),
        'note': 'Only required when Performance Input Method = NominalEfficiency.'},
    ('ElectricLoadCenter:Transformer', 'Per_Unit_Load_for_Nameplate_Efficiency'): {
        'by': 'Performance_Input_Method', 'when': ('NominalEfficiency',)},
    ('ElectricLoadCenter:Transformer', 'Reference_Temperature_for_Nameplate_Efficiency'): {
        'by': 'Performance_Input_Method', 'when': ('NominalEfficiency',)},
    ('ElectricLoadCenter:Transformer', 'Per_Unit_Load_for_Maximum_Efficiency'): {
        'by': 'Performance_Input_Method', 'when': ('NominalEfficiency',)},
    ('ElectricLoadCenter:Transformer', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',),
        'note': 'Not used if Zone Name is left blank (transformer losses dissipated outdoors).'},
    ('ElectricLoadCenter:Transformer', 'Consider_Transformer_Loss_for_Utility_Cost'): {
        'by': 'Transformer_Usage', 'when': ('PowerInFromGrid',),
        'note': 'Only required when the transformer is used for power in from the utility grid.'},
    ('ElectricLoadCenter:Transformer', 'Meter_1_Name'): {
        'by': 'Transformer_Usage', 'when': ('PowerInFromGrid',),
        'note': 'Meter 1..10 Name fields (extensible) only required for PowerInFromGrid transformers.'},

    ('ElectricLoadCenter:Distribution', 'Inverter_Name'): {
        'by': 'Electrical_Buss_Type',
        'when': ('DirectCurrentWithInverter', 'DirectCurrentWithInverterDCStorage', 'DirectCurrentWithInverterACStorage'),
        'note': 'Required only for the three DC-with-inverter buss types.'},
    ('ElectricLoadCenter:Distribution', 'Electrical_Storage_Object_Name'): {
        'by': 'Electrical_Buss_Type',
        'when': ('AlternatingCurrentWithStorage', 'DirectCurrentWithInverterDCStorage', 'DirectCurrentWithInverterACStorage'),
        'note': 'Required only for buss types that include storage.'},
    ('ElectricLoadCenter:Distribution', 'Generator_Demand_Limit_Scheme_Purchased_Electric_Demand_Limit'): {
        'by': 'Generator_Operation_Scheme_Type', 'when': ('DemandLimit',)},
    ('ElectricLoadCenter:Distribution', 'Generator_Track_Schedule_Name_Scheme_Schedule_Name'): {
        'by': 'Generator_Operation_Scheme_Type', 'when': ('TrackSchedule',)},
    ('ElectricLoadCenter:Distribution', 'Generator_Track_Meter_Scheme_Meter_Name'): {
        'by': 'Generator_Operation_Scheme_Type', 'when': ('TrackMeter',)},
    ('ElectricLoadCenter:Distribution', 'Storage_Control_Track_Meter_Name'): {
        'by': 'Storage_Operation_Scheme', 'when': ('TrackMeterDemandStoreExcessOnSite',)},
    ('ElectricLoadCenter:Distribution', 'Storage_Converter_Object_Name'): {
        'by': 'Storage_Operation_Scheme', 'when': ('FacilityDemandLeveling', 'TrackChargeDischargeSchedules'),
        'note': 'IDD note: "a converter is expected" for these two schemes (not phrased as \\required-field, but functionally needed to charge storage from the grid).'},
    ('ElectricLoadCenter:Distribution', 'Design_Storage_Control_Charge_Power'): {
        'by': 'Storage_Operation_Scheme', 'when': ('FacilityDemandLeveling', 'TrackChargeDischargeSchedules')},
    ('ElectricLoadCenter:Distribution', 'Storage_Charge_Power_Fraction_Schedule_Name'): {
        'by': 'Storage_Operation_Scheme', 'when': ('TrackChargeDischargeSchedules',)},
    ('ElectricLoadCenter:Distribution', 'Design_Storage_Control_Discharge_Power'): {
        'by': 'Storage_Operation_Scheme', 'when': ('FacilityDemandLeveling', 'TrackChargeDischargeSchedules')},
    ('ElectricLoadCenter:Distribution', 'Storage_Discharge_Power_Fraction_Schedule_Name'): {
        'by': 'Storage_Operation_Scheme', 'when': ('TrackChargeDischargeSchedules',)},
    ('ElectricLoadCenter:Distribution', 'Storage_Control_Utility_Demand_Target'): {
        'by': 'Storage_Operation_Scheme', 'when': ('FacilityDemandLeveling',)},
    ('ElectricLoadCenter:Distribution', 'Storage_Control_Utility_Demand_Target_Fraction_Schedule_Name'): {
        'by': 'Storage_Operation_Scheme', 'when': ('FacilityDemandLeveling',)},

    ('ElectricLoadCenter:Inverter:Simple', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',), 'note': 'If Zone Name is blank the inverter is assumed outdoors and this field is not used.'},
    ('ElectricLoadCenter:Inverter:FunctionOfPower', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Inverter:LookUpTable', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Storage:Simple', 'Radiative_Fraction_for_Zone_Heat_Gains'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Storage:Battery', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Storage:LiIonNMCBattery', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Storage:Converter', 'Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<non-blank>',)},
    ('ElectricLoadCenter:Storage:Converter', 'Simple_Fixed_Efficiency'): {
        'by': 'Power_Conversion_Efficiency_Method', 'when': ('SimpleFixed',)},
    ('ElectricLoadCenter:Storage:Converter', 'Design_Maximum_Continuous_Input_Power'): {
        'by': 'Power_Conversion_Efficiency_Method', 'when': ('FunctionOfPower',)},
    ('ElectricLoadCenter:Storage:Converter', 'Efficiency_Function_of_Power_Curve_Name'): {
        'by': 'Power_Conversion_Efficiency_Method', 'when': ('FunctionOfPower',)},

    ('ElectricLoadCenter:Generators', 'Generator_1_Rated_Thermal_to_Electrical_Power_Ratio'): {
        'by': 'ElectricLoadCenter:Distribution.Generator_Operation_Scheme_Type', 'when': ('FollowThermal', 'FollowThermalLimitElectrical'),
        'note': 'Cross-object gate: this ratio (repeated per extensible Generator <n> block) is only used for dispatch when the referencing ElectricLoadCenter:Distribution has Generator Operation Scheme Type = FollowThermal or FollowThermalLimitElectrical; it does not feed the individual generator performance models.'},

    ('Generator:MicroTurbine', 'Reference_Heat_Recovery_Water_Flow_Rate'): {
        'by': 'Heat_Recovery_Water_Flow_Operating_Mode', 'when': ('InternalControl',),
        'note': 'Required when InternalControl is selected; under PlantControl the flow rate is supplied externally by the plant.'},
    ('Generator:MicroTurbine', 'Heat_Recovery_Water_Flow_Rate_Function_of_Temperature_and_Power_Curve_Name'): {
        'by': 'Heat_Recovery_Water_Flow_Operating_Mode', 'when': ('InternalControl',),
        'note': 'Only used if InternalControl is selected; if left blank under InternalControl the flow rate is constant at the reference value.'},
    ('Generator:MicroCHP:NonNormalizedParameters', 'Cooling_Water_Flow_Rate_Curve_Name'): {
        'by': 'Cooling_Water_Flow_Rate_Mode', 'when': ('InternalControl',)},

    ('Generator:FuelCell:PowerModule', 'Constant_Skin_Loss_Rate'): {
        'by': 'Skin_Loss_Calculation_Mode', 'when': ('ConstantRate',)},
    ('Generator:FuelCell:PowerModule', 'Skin_Loss_U_Factor_Times_Area_Term'): {
        'by': 'Skin_Loss_Calculation_Mode', 'when': ('UAForProcessGasTemperature',)},
    ('Generator:FuelCell:PowerModule', 'Skin_Loss_Quadratic_Curve_Name'): {
        'by': 'Skin_Loss_Calculation_Mode', 'when': ('QuadraticFunctionOfFuelRate',)},

    ('Generator:FuelCell:AirSupply', 'Stoichiometric_Ratio'): {
        'by': 'Air_Supply_Rate_Calculation_Mode', 'when': ('AirRatiobyStoics',)},
    ('Generator:FuelCell:AirSupply', 'Air_Rate_Function_of_Electric_Power_Curve_Name'): {
        'by': 'Air_Supply_Rate_Calculation_Mode', 'when': ('QuadraticFunctionofElectricPower',)},
    ('Generator:FuelCell:AirSupply', 'Air_Rate_Function_of_Fuel_Rate_Curve_Name'): {
        'by': 'Air_Supply_Rate_Calculation_Mode', 'when': ('QuadraticFunctionofFuelRate',)},
    ('Generator:FuelCell:AirSupply', 'Number_of_UserDefined_Constituents'): {
        'by': 'Air_Supply_Constituent_Mode', 'when': ('UserDefinedConstituents',)},
    ('Generator:FuelCell:AirSupply', 'Constituent_1_Name'): {
        'by': 'Air_Supply_Constituent_Mode', 'when': ('UserDefinedConstituents',),
        'note': 'Constituent 1-5 Name / Molar Fraction 1-5 (extensible pair) only used under UserDefinedConstituents; ignored (composition fixed) under AmbientAir.'},

    ('Generator:FuelCell:WaterSupply', 'Water_Temperature_Reference_Node_Name'): {
        'by': 'Water_Temperature_Modeling_Mode', 'when': ('TemperatureFromAirNode', 'TemperatureFromWaterNode')},
    ('Generator:FuelCell:WaterSupply', 'Water_Temperature_Schedule_Name'): {
        'by': 'Water_Temperature_Modeling_Mode', 'when': ('TemperatureFromSchedule',)},

    ('Generator:FuelCell:AuxiliaryHeater', 'Zone_Name_to_Receive_Skin_Losses'): {
        'by': 'Skin_Loss_Destination', 'when': ('SurroundingZone',)},
    ('Generator:FuelCell:AuxiliaryHeater', 'Maximum_Heating_Capacity_in_Watts'): {
        'by': 'Heating_Capacity_Units', 'when': ('Watts',)},
    ('Generator:FuelCell:AuxiliaryHeater', 'Minimum_Heating_Capacity_in_Watts'): {
        'by': 'Heating_Capacity_Units', 'when': ('Watts',)},
    ('Generator:FuelCell:AuxiliaryHeater', 'Maximum_Heating_Capacity_in_Kmol_per_Second'): {
        'by': 'Heating_Capacity_Units', 'when': ('kmol/s',)},
    ('Generator:FuelCell:AuxiliaryHeater', 'Minimum_Heating_Capacity_in_Kmol_per_Second'): {
        'by': 'Heating_Capacity_Units', 'when': ('kmol/s',)},

    ('Generator:FuelCell:ExhaustGasToWaterHeatExchanger', 'Method_1_Heat_Exchanger_Effectiveness'): {
        'by': 'Heat_Exchanger_Calculation_Method', 'when': ('FixedEffectiveness',)},
    ('Generator:FuelCell:ExhaustGasToWaterHeatExchanger', 'Method_2_Parameter_hxs0'): {
        'by': 'Heat_Exchanger_Calculation_Method', 'when': ('EmpiricalUAeff',)},
    ('Generator:FuelCell:ExhaustGasToWaterHeatExchanger', 'Method_3_h0Gas_Coefficient'): {
        'by': 'Heat_Exchanger_Calculation_Method', 'when': ('FundementalUAeff',)},
    ('Generator:FuelCell:ExhaustGasToWaterHeatExchanger', 'Method_4_hxl1_Coefficient'): {
        'by': 'Heat_Exchanger_Calculation_Method', 'when': ('Condensing',)},

    ('Generator:FuelCell:Inverter', 'Efficiency_Function_of_DC_Power_Curve_Name'): {
        'by': 'Inverter_Efficiency_Calculation_Mode', 'when': ('Quadratic',)},
    ('Generator:FuelCell:Inverter', 'Inverter_Efficiency'): {
        'by': 'Inverter_Efficiency_Calculation_Mode', 'when': ('Constant',)},

    ('Generator:FuelCell', 'Fuel_Temperature_Reference_Node_Name'): {
        'by': 'Fuel_Temperature_Modeling_Mode', 'when': ('TemperatureFromAirNode',)},
    ('Generator:FuelCell', 'Fuel_Temperature_Schedule_Name'): {
        'by': 'Fuel_Temperature_Modeling_Mode', 'when': ('Scheduled',)},

    ('PhotovoltaicPerformance:Simple', 'Value_for_Cell_Efficiency_if_Fixed'): {
        'by': 'Conversion_Efficiency_Input_Mode', 'when': ('Fixed',)},
    ('PhotovoltaicPerformance:Simple', 'Efficiency_Schedule_Name'): {
        'by': 'Conversion_Efficiency_Input_Mode', 'when': ('Scheduled',)},

    ('Generator:PVWatts', 'Tilt_Angle'): {
        'by': 'Array_Geometry_Type', 'when': ('TiltAzimuth',)},
    ('Generator:PVWatts', 'Azimuth_Angle'): {
        'by': 'Array_Geometry_Type', 'when': ('TiltAzimuth',)},
    ('Generator:PVWatts', 'Surface_Name'): {
        'by': 'Array_Geometry_Type', 'when': ('Surface',)},
    ('Generator:PVWatts', 'Ground_Coverage_Ratio'): {
        'by': 'Array_Type', 'when': ('OneAxis', 'OneAxisBacktracking'),
        'note': 'IDD note: "Applies only to arrays with one-axis tracking"; has no effect for FixedOpenRack/FixedRoofMounted/TwoAxis.'},

    ('Generator:WindTurbine', 'Maximum_Power_Coefficient'): {
        'by': 'Rotor_Type', 'when': ('HorizontalAxisWindTurbine',)},
    ('Generator:WindTurbine', 'Blade_Drag_Coefficient'): {
        'by': 'Rotor_Type', 'when': ('VerticalAxisWindTurbine',)},
    ('Generator:WindTurbine', 'Blade_Lift_Coefficient'): {
        'by': 'Rotor_Type', 'when': ('VerticalAxisWindTurbine',)},

    # --- Operational Faults ---
    ('FaultModel:Fouling:Coil', 'UAFouled'): {
        'by': 'Fouling_Input_Method', 'when': ('FouledUARated',)},
    ('FaultModel:Fouling:Coil', 'Water_Side_Fouling_Factor'): {
        'by': 'Fouling_Input_Method', 'when': ('FoulingFactor',)},
    ('FaultModel:Fouling:Coil', 'Air_Side_Fouling_Factor'): {
        'by': 'Fouling_Input_Method', 'when': ('FoulingFactor',)},
    ('FaultModel:Fouling:Coil', 'Outside_Coil_Surface_Area'): {
        'by': 'Fouling_Input_Method', 'when': ('FoulingFactor',)},
    ('FaultModel:Fouling:Coil', 'Inside_to_Outside_Coil_Surface_Area_Ratio'): {
        'by': 'Fouling_Input_Method', 'when': ('FoulingFactor',)},
    ('FaultModel:HumidistatOffset', 'Availability_Schedule_Name'): {
        'by': 'Humidistat_Offset_Type', 'when': ('ThermostatOffsetIndependent',)},
    ('FaultModel:HumidistatOffset', 'Severity_Schedule_Name'): {
        'by': 'Humidistat_Offset_Type', 'when': ('ThermostatOffsetIndependent',)},
    ('FaultModel:HumidistatOffset', 'Reference_Humidistat_Offset'): {
        'by': 'Humidistat_Offset_Type', 'when': ('ThermostatOffsetIndependent',)},
    ('FaultModel:HumidistatOffset', 'Related_Thermostat_Offset_Fault_Name'): {
        'by': 'Humidistat_Offset_Type', 'when': ('ThermostatOffsetDependent',)},
    ('FaultModel:TemperatureSensorOffset:CoilSupplyAir', 'Water_Coil_Controller_Name'): {
        'by': 'Coil_Object_Type', 'when': ('Coil:Heating:Water', 'Coil:Cooling:Water', 'Coil:Cooling:Water:Detailedgeometry'),
        'note': 'IDD note: required for water coils; the IDD spells the DetailedGeometry key "Coil:Cooling:Water:Detailedgeometry" (lowercase g) -- see IDD_DISAGREEMENTS.'},

    # --- Fluid Properties ---
    ('FluidProperties:GlycolConcentration', 'User_Defined_Glycol_Name'): {
        'by': 'Glycol_Type', 'when': ('UserDefinedGlycolType',)},

    # --- Table:Lookup / Table:IndependentVariable (Performance Tables) ---
    ('Table:Lookup', 'Normalization_Divisor'): {
        'by': 'Normalization_Method', 'when': ('DivisorOnly', 'AutomaticWithDivisor')},
    ('Table:Lookup', 'External_File_Column_Number'): {
        'by': 'External_File_Name', 'when': ('<non-blank>',)},
    ('Table:Lookup', 'External_File_Starting_Row_Number'): {
        'by': 'External_File_Name', 'when': ('<non-blank>',)},
    ('Table:Lookup', 'Output_Value_1'): {
        'by': 'External_File_Name', 'when': ('<blank>',),
        'note': 'Inverse gate: Output Value <n> fields are only read when External File Name is blank; when a file is given the file supplies the output values instead.'},
    ('Table:IndependentVariable', 'External_File_Column_Number'): {
        'by': 'External_File_Name', 'when': ('<non-blank>',)},
    ('Table:IndependentVariable', 'External_File_Starting_Row_Number'): {
        'by': 'External_File_Name', 'when': ('<non-blank>',)},
    ('Table:IndependentVariable', 'Value_1'): {
        'by': 'External_File_Name', 'when': ('<blank>',),
        'note': 'Inverse gate: Value <n> fields are only read when External File Name is blank.'},

    # --- Hybrid Model ---
    ('HybridModel:Zone', 'Zone_Measured_Air_Temperature_Schedule_Name'): {
        'by': 'Calculate_Zone_Air_Infiltration_Rate', 'when': ('Yes',),
        'note': 'One of the temperature/humidity-ratio/CO2 measured-schedule combinations (per IDD field notes) must be supplied when this is Yes; ignored when No.'},
    ('HybridModel:Zone', 'Zone_Measured_Air_Humidity_Ratio_Schedule_Name'): {
        'by': 'Calculate_Zone_Air_Infiltration_Rate', 'when': ('Yes',)},
    ('HybridModel:Zone', 'Zone_Measured_Air_CO2_Concentration_Schedule_Name'): {
        'by': 'Calculate_Zone_Air_Infiltration_Rate', 'when': ('Yes',)},
    ('HybridModel:Zone', 'Zone_Input_Supply_Air_Temperature_Schedule_Name'): {
        'by': 'Calculate_Zone_Air_Infiltration_Rate', 'when': ('Yes',),
        'note': 'Needed together with Zone Input Supply Air Mass Flow Rate Schedule Name only for the "HVAC is on" measurement case.'},
    ('HybridModel:Zone', 'Zone_Input_Supply_Air_Mass_Flow_Rate_Schedule_Name'): {
        'by': 'Calculate_Zone_Air_Infiltration_Rate', 'when': ('Yes',)},
    ('HybridModel:Zone', 'Zone_Input_People_Activity_Schedule_Name'): {
        'by': 'Calculate_Zone_People_Count', 'when': ('Yes',),
        'note': 'Optional overrides of default people-related constants; only consulted when Calculate Zone People Count = Yes.'},
    ('HybridModel:Zone', 'Zone_Input_People_Sensible_Heat_Fraction_Schedule_Name'): {
        'by': 'Calculate_Zone_People_Count', 'when': ('Yes',)},
    ('HybridModel:Zone', 'Zone_Input_People_Radiant_Heat_Fraction_Schedule_Name'): {
        'by': 'Calculate_Zone_People_Count', 'when': ('Yes',)},
    ('HybridModel:Zone', 'Zone_Input_People_CO2_Generation_Rate_Schedule_Name'): {
        'by': 'Calculate_Zone_People_Count', 'when': ('Yes',)},

    # --- User Defined HVAC and Plant Component Models ---
    ('Coil:UserDefined', 'Air_Connection_2_Inlet_Node_Name'): {
        'by': 'Number_of_Air_Connections', 'when': (2,),
        'note': 'Secondary air stream nodes are only meaningful/required when Number of Air Connections = 2; left blank/unused for 1.'},
    ('Coil:UserDefined', 'Air_Connection_2_Outlet_Node_Name'): {
        'by': 'Number_of_Air_Connections', 'when': (2,)},
    ('Coil:UserDefined', 'Plant_Connection_Inlet_Node_Name'): {
        'by': 'Plant_Connection_is_Used', 'when': ('Yes',)},
    ('Coil:UserDefined', 'Plant_Connection_Outlet_Node_Name'): {
        'by': 'Plant_Connection_is_Used', 'when': ('Yes',)},
    ('PlantComponent:UserDefined', 'Plant_Connection_2_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (2, 3, 4),
        'note': 'Connection 2/3/4 node, loading-mode and flow-request-mode fields are only active up to the count given in Number of Plant Loop Connections (1-4).'},
    ('PlantComponent:UserDefined', 'Plant_Connection_3_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (3, 4)},
    ('PlantComponent:UserDefined', 'Plant_Connection_4_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (4,)},
    ('ZoneHVAC:ForcedAir:UserDefined', 'Plant_Connection_2_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (2, 3)},
    ('ZoneHVAC:ForcedAir:UserDefined', 'Plant_Connection_3_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (3,)},
    ('AirTerminal:SingleDuct:UserDefined', 'Plant_Connection_2_Inlet_Node_Name'): {
        'by': 'Number_of_Plant_Loop_Connections', 'when': (2,)},

    # --- HVAC Template Objects (recurring, explicitly-documented patterns) ---
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Heating_Air_Flow_Rate'): {
        'by': 'Heating_Limit', 'when': ('LimitFlowRate', 'LimitFlowRateAndCapacity'),
        'note': 'IDD note: ignored if Heating Limit = NoLimit.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Sensible_Heating_Capacity'): {
        'by': 'Heating_Limit', 'when': ('LimitCapacity', 'LimitFlowRateAndCapacity'),
        'note': 'IDD note: ignored if Heating Limit = NoLimit.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Cooling_Air_Flow_Rate'): {
        'by': 'Cooling_Limit', 'when': ('LimitFlowRate', 'LimitFlowRateAndCapacity'),
        'note': 'IDD note: ignored if Cooling Limit = NoLimit; also required if Outdoor Air Economizer Type != NoEconomizer.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Total_Cooling_Capacity'): {
        'by': 'Cooling_Limit', 'when': ('LimitCapacity', 'LimitFlowRateAndCapacity'),
        'note': 'IDD note: ignored if Cooling Limit = NoLimit.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Cooling_Sensible_Heat_Ratio'): {
        'by': 'Dehumidification_Control_Type', 'when': ('ConstantSensibleHeatRatio',),
        'note': 'IDD note: applicable only when Dehumidification Control Type is ConstantSensibleHeatRatio.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Latent_Heat_Recovery_Effectiveness'): {
        'by': 'Heat_Recovery_Type', 'when': ('Enthalpy',),
        'note': 'IDD note: applicable only if Heat Recovery Type is Enthalpy.'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Design_Specification_Outdoor_Air_Object_Name'): {
        'by': 'Outdoor_Air_Method', 'when': ('DetailedSpecification',)},

    # Zone Minimum Air Flow Input Method: recurs on VAV-family zone templates
    # (HVACTemplate:Zone:VAV, VAV:FanPowered, VAV:HeatAndCool, DualDuct, and
    # the corresponding zone-terminal fields on the HVACTemplate:System:VAV
    # family).
    ('HVACTemplate:Zone:VAV', 'Constant_Minimum_Air_Flow_Fraction'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Constant', 'Scheduled'),
        'note': 'Required if Constant; optional (used only for reheat-coil sizing) if Scheduled; not used if FixedFlowRate.'},
    ('HVACTemplate:Zone:VAV', 'Fixed_Minimum_Air_Flow_Rate'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('FixedFlowRate', 'Scheduled')},
    ('HVACTemplate:Zone:VAV', 'Minimum_Air_Flow_Fraction_Schedule_Name'): {
        'by': 'Zone_Minimum_Air_Flow_Input_Method', 'when': ('Scheduled',)},

    # Zone Cooling/Heating Design Supply Air Temperature Input Method: recurs
    # on every HVACTemplate:Zone:* object with its own sizing block (VAV,
    # VAV:FanPowered, VAV:HeatAndCool, ConstantVolume, DualDuct, Unitary,
    # WaterToAirHeatPump, PTAC, PTHP).
    ('HVACTemplate:Zone:VAV', 'Zone_Cooling_Design_Supply_Air_Temperature_Difference'): {
        'by': 'Zone_Cooling_Design_Supply_Air_Temperature_Input_Method', 'when': ('TemperatureDifference',)},
    ('HVACTemplate:Zone:VAV', 'Zone_Heating_Design_Supply_Air_Temperature_Difference'): {
        'by': 'Zone_Heating_Design_Supply_Air_Temperature_Input_Method', 'when': ('TemperatureDifference',)},
    ('HVACTemplate:Zone:VAV', 'Design_Specification_Outdoor_Air_Object_Name'): {
        'by': 'Outdoor_Air_Method', 'when': ('DetailedSpecification',)},
    ('HVACTemplate:Zone:VAV', 'Design_Specification_Zone_Air_Distribution_Object_Name'): {
        'by': 'Outdoor_Air_Method', 'when': ('DetailedSpecification',)},

    ('HVACTemplate:System:VAV', 'Economizer_Maximum_Limit_Dewpoint_Temperature'): {
        'by': 'Economizer_Type', 'when': ('FixedDewPointAndDryBulb',),
        'note': 'IDD note: for FixedDewPointAndDryBulb economizer control type; no effect for other Economizer Type keys.'},
    ('HVACTemplate:System:VAV', 'Night_Cycle_Control_Zone_Name'): {
        'by': 'Night_Cycle_Control', 'when': ('CycleOnControlZone',),
        'note': 'IDD note: applicable only if Night Cycle Control is CycleOnControlZone.'},

    # Condenser Type recurs on unitary/DX-coil HVACTemplate:Zone/System
    # objects (e.g. HVACTemplate:Zone:Unitary, System:Unitary,
    # System:UnitaryHeatPump:AirToAir, System:UnitarySystem).
    ('HVACTemplate:Zone:Unitary', 'Water_Condenser_Volume_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'IDD note: only used when Condenser Type = WaterCooled.'},
    ('HVACTemplate:Zone:Unitary', 'Evaporative_Condenser_Air_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',)},
    ('HVACTemplate:Zone:Unitary', 'Evaporative_Condenser_Effectiveness'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',)},
    ('HVACTemplate:Zone:Unitary', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',)},
    ('HVACTemplate:Zone:Unitary', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',),
        'note': 'Also only active during periods the Basin Heater Operating Schedule allows.'},
    ('HVACTemplate:Zone:Unitary', 'Resistive_Defrost_Heater_Capacity'): {
        'by': 'Defrost_Strategy', 'when': ('Resistive',),
        'note': 'IDD note: only applicable if resistive defrost strategy is specified.'},
    ('HVACTemplate:Zone:Unitary', 'Defrost_Time_Period_Fraction'): {
        'by': 'Defrost_Control', 'when': ('Timed',),
        'note': 'IDD note: only applicable if Timed defrost control is specified.'},

    ('HVACTemplate:Plant:Chiller', 'Condenser_Type'): {
        'by': 'Chiller_Type', 'when': ('ElectricCentrifugalChiller', 'ElectricScrewChiller', 'ElectricReciprocatingChiller'),
        'note': 'IDD note: not applicable if Chiller Type is DistrictChilledWater.'},
    ('HVACTemplate:Plant:Chiller', 'Nominal_COP'): {
        'by': 'Chiller_Type', 'when': ('ElectricCentrifugalChiller', 'ElectricScrewChiller', 'ElectricReciprocatingChiller'),
        'note': 'IDD note: not applicable if Chiller Type is DistrictChilledWater (field is nonetheless \\required-field in the IDD -- see IDD_DISAGREEMENTS).'},
}

METHOD_GROUPS = {
    ('ElectricLoadCenter:Transformer', 'Performance_Input_Method'): {
        'RatedLosses': 'sizing from Rated No Load Loss + Rated Load Loss',
        'NominalEfficiency': 'sizing from Nameplate Efficiency + Per Unit Load for Nameplate/Maximum Efficiency + Reference Temperature for Nameplate Efficiency'},
    ('ElectricLoadCenter:Distribution', 'Generator_Operation_Scheme_Type'): {
        'Baseload': 'all generators run at rated power whenever available',
        'DemandLimit': 'generators dispatched to keep purchased electric demand under Generator Demand Limit Scheme Purchased Electric Demand Limit',
        'TrackElectrical': 'generators dispatched to track total facility electric demand',
        'TrackSchedule': 'generators dispatched to track Generator Track Schedule Name Scheme Schedule Name',
        'TrackMeter': 'generators dispatched to track Generator Track Meter Scheme Meter Name',
        'FollowThermal': 'generators dispatched by thermal load, using each generator entry\'s Rated Thermal to Electrical Power Ratio',
        'FollowThermalLimitElectrical': 'same as FollowThermal but electrical output is capped at rated electrical power'},
    ('ElectricLoadCenter:Distribution', 'Electrical_Buss_Type'): {
        'AlternatingCurrent': 'simplest arrangement, no inverter or storage object referenced',
        'AlternatingCurrentWithStorage': 'adds Electrical Storage Object Name (AC-side storage)',
        'DirectCurrentWithInverter': 'adds Inverter Name (DC generators through an inverter to the AC buss)',
        'DirectCurrentWithInverterDCStorage': 'adds Inverter Name and Electrical Storage Object Name, storage on the DC side',
        'DirectCurrentWithInverterACStorage': 'adds Inverter Name and Electrical Storage Object Name, storage on the AC side'},
    ('ElectricLoadCenter:Distribution', 'Storage_Operation_Scheme'): {
        'TrackFacilityElectricDemandStoreExcessOnSite': 'legacy behavior: only excess on-site generation gets stored',
        'TrackMeterDemandStoreExcessOnSite': 'like the above but keyed off Storage Control Track Meter Name instead of the facility meter',
        'TrackChargeDischargeSchedules': 'charge/discharge power and timing come from Design/Fraction-Schedule charge and discharge fields',
        'FacilityDemandLeveling': 'storage charges/discharges to hold facility grid demand at Storage Control Utility Demand Target'},
    ('ElectricLoadCenter:Storage:Converter', 'Power_Conversion_Efficiency_Method'): {
        'SimpleFixed': 'constant AC-to-DC efficiency from Simple Fixed Efficiency',
        'FunctionOfPower': 'efficiency varies with normalized power via Efficiency Function of Power Curve Name, referenced to Design Maximum Continuous Input Power'},
    ('Generator:MicroTurbine', 'Heat_Recovery_Water_Flow_Operating_Mode'): {
        'PlantControl': 'heat recovery water flow rate is determined externally by the plant',
        'InternalControl': 'generator controls its own heat recovery flow, using Reference Heat Recovery Water Flow Rate and optionally a temperature/power modifier curve'},
    ('Generator:MicroCHP:NonNormalizedParameters', 'Cooling_Water_Flow_Rate_Mode'): {
        'PlantControl': 'cooling water flow rate set by the plant', 'InternalControl': 'flow rate computed from Cooling Water Flow Rate Curve Name'},
    ('Generator:FuelCell:PowerModule', 'Efficiency_Curve_Mode'): {
        'Annex42': 'non-normalized efficiency curve, sized for one specific FC product',
        'Normalized': 'normalized efficiency curve (standard EnergyPlus practice); note the accompanying Nominal Efficiency/Nominal Electrical Power fields are explicitly marked "not used" in the IDD regardless of mode -- see IDD_DISAGREEMENTS'},
    ('Generator:FuelCell:PowerModule', 'Skin_Loss_Calculation_Mode'): {
        'ConstantRate': 'fixed skin loss rate from Constant Skin Loss Rate',
        'UAForProcessGasTemperature': 'skin loss from Skin Loss U-Factor Times Area Term times a process-gas temperature difference',
        'QuadraticFunctionOfFuelRate': 'skin loss from Skin Loss Quadratic Curve Name evaluated at fuel use rate'},
    ('Generator:FuelCell:AirSupply', 'Air_Supply_Rate_Calculation_Mode'): {
        'AirRatiobyStoics': 'air rate from Stoichiometric Ratio (excess air ratio)',
        'QuadraticFunctionofElectricPower': 'air rate from Air Rate Function of Electric Power Curve Name',
        'QuadraticFunctionofFuelRate': 'air rate from Air Rate Function of Fuel Rate Curve Name'},
    ('Generator:FuelCell:AirSupply', 'Air_Supply_Constituent_Mode'): {
        'AmbientAir': 'fixed composition (77.28% N2, 20.73% O2, 1.04% H2O, 0.92% Ar, 0.03% CO2), Constituent fields ignored',
        'UserDefinedConstituents': 'composition from Number of UserDefined Constituents + Constituent <n> Name / Molar Fraction <n> pairs (up to 5)'},
    ('Generator:FuelCell:WaterSupply', 'Water_Temperature_Modeling_Mode'): {
        'TemperatureFromAirNode': 'water inlet temperature taken from the node in Water Temperature Reference Node Name',
        'TemperatureFromWaterNode': 'same node-based lookup, node is a water node',
        'TemperatureFromSchedule': 'water inlet temperature taken from Water Temperature Schedule Name',
        'MainsWaterTemperature': 'water inlet temperature taken from Site Water Mains Temperature'},
    ('Generator:FuelCell:AuxiliaryHeater', 'Skin_Loss_Destination'): {
        'SurroundingZone': 'skin losses delivered to the zone named in Zone Name to Receive Skin Losses',
        'AirInletForFuelCell': 'skin losses delivered to the fuel cell air inlet stream'},
    ('Generator:FuelCell:AuxiliaryHeater', 'Heating_Capacity_Units'): {
        'Watts': 'capacity limits given by Maximum/Minimum Heating Capacity in Watts',
        'kmol/s': 'capacity limits given by Maximum/Minimum Heating Capacity in Kmol per Second'},
    ('Generator:FuelCell:ExhaustGasToWaterHeatExchanger', 'Heat_Exchanger_Calculation_Method'): {
        'FixedEffectiveness': 'method 1: constant Method 1 Heat Exchanger Effectiveness',
        'EmpiricalUAeff': 'method 2: effective UA from empirical Method 2 Parameter hxs0-hxs4',
        'FundementalUAeff': 'method 3: effective UA from Method 3 h0Gas/NdotGasRef/n/Gas Area/h0 Water/N dot Water ref/m/Water Area/F Adjustment Factor coefficients',
        'Condensing': 'method 4: LMTD heat exchange plus condensation, using Method 2 hxs1-hxs4 and Method 4 hxl1/hxl2/Condensation Threshold'},
    ('Generator:FuelCell:Inverter', 'Inverter_Efficiency_Calculation_Mode'): {
        'Quadratic': 'efficiency from Efficiency Function of DC Power Curve Name', 'Constant': 'fixed Inverter Efficiency value'},
    ('Generator:FuelCell', 'Fuel_Temperature_Modeling_Mode'): {
        'TemperatureFromAirNode': 'fuel temperature equals the temperature at Fuel Temperature Reference Node Name',
        'Scheduled': 'fuel temperature taken from Fuel Temperature Schedule Name'},
    ('Generator:Photovoltaic', 'Photovoltaic_Performance_Object_Type'): {
        'PhotovoltaicPerformance:Simple': 'Module Performance Name must reference a PhotovoltaicPerformance:Simple object',
        'PhotovoltaicPerformance:EquivalentOne-Diode': 'Module Performance Name must reference a PhotovoltaicPerformance:EquivalentOne-Diode object',
        'PhotovoltaicPerformance:Sandia': 'Module Performance Name must reference a PhotovoltaicPerformance:Sandia object'},
    ('PhotovoltaicPerformance:Simple', 'Conversion_Efficiency_Input_Mode'): {
        'Fixed': 'constant cell efficiency from Value for Cell Efficiency if Fixed', 'Scheduled': 'cell efficiency taken from Efficiency Schedule Name'},
    ('Generator:PVWatts', 'Array_Geometry_Type'): {
        'TiltAzimuth': 'unshaded array; geometry from Tilt Angle + Azimuth Angle', 'Surface': 'geometry and shading taken from the surface in Surface Name'},
    ('Generator:WindTurbine', 'Rotor_Type'): {
        'HorizontalAxisWindTurbine': 'enables Maximum Power Coefficient and the optional Power Coefficient C1-C6 analytic-approximation set',
        'VerticalAxisWindTurbine': 'requires Blade Drag Coefficient and Blade Lift Coefficient; Rotor Diameter is the perpendicular circle diameter from the ground pole'},
    ('Generator:WindTurbine', 'Power_Control'): {
        'FixedSpeedFixedPitch': 'constant power above rated wind speed; user should input maximum power as Rated Power',
        'FixedSpeedVariablePitch': 'blade pitch varies to hold constant power above rated wind speed',
        'VariableSpeedFixedPitch': 'rotor speed varies, pitch fixed',
        'VariableSpeedVariablePitch': 'default; both rotor speed and pitch vary'},

    ('FaultModel:Fouling:Coil', 'Fouling_Input_Method'): {
        'FouledUARated': 'fouled performance given directly as UAFouled',
        'FoulingFactor': 'fouled performance derived from Water Side Fouling Factor, Air Side Fouling Factor, Outside Coil Surface Area and Inside to Outside Coil Surface Area Ratio'},
    ('FaultModel:HumidistatOffset', 'Humidistat_Offset_Type'): {
        'ThermostatOffsetIndependent': 'offset driven by its own Availability/Severity Schedule Name and Reference Humidistat Offset',
        'ThermostatOffsetDependent': 'offset driven by the paired FaultModel:ThermostatOffset named in Related Thermostat Offset Fault Name; the independent schedule/offset fields are not used'},

    ('FluidProperties:GlycolConcentration', 'Glycol_Type'): {
        'EthyleneGlycol': 'built-in property data, User Defined Glycol Name not used',
        'PropyleneGlycol': 'built-in property data, User Defined Glycol Name not used',
        'UserDefinedGlycolType': 'properties taken from a FluidProperties:Name/Saturated/Superheated/Concentration set named via User Defined Glycol Name'},

    ('Table:Lookup', 'Normalization_Method'): {
        'None': 'raw Output Value <n> data used as-is',
        'DivisorOnly': 'every output value divided by Normalization Divisor',
        'AutomaticWithDivisor': 'output values normalized so the value at the Normalization Reference Value point is 1.0, then further divided by Normalization Divisor'},
    ('Table:IndependentVariable', 'Interpolation_Method'): {
        'Linear': 'linear interpolation between listed values', 'Cubic': 'cubic spline interpolation between listed values'},
    ('Table:IndependentVariable', 'Extrapolation_Method'): {
        'Constant': 'value held constant beyond Minimum/Maximum Value (with a warning)', 'Linear': 'value extrapolated linearly beyond Minimum/Maximum Value'},

    ('PlantComponent:UserDefined', 'Plant_Connection_1_Loading_Mode'): {
        'DemandsLoad': 'component behaves as a passive load on the loop',
        'MeetsLoadWithPassiveCapacity': 'component has capacity but does not actively control it',
        'MeetsLoadWithNominalCapacity': 'component actively meets the load with its nominal capacity, no outlet temperature limit',
        'MeetsLoadWithNominalCapacityLowOutLimit': 'same, with a lower limit on outlet fluid temperature',
        'MeetsLoadWithNominalCapacityHiOutLimit': 'same, with an upper limit on outlet fluid temperature',
        'note': 'Connection 2/3/4 Loading Mode fields use differently-spelled IDD keys (MeetLoadWith... without the "s") -- see IDD_DISAGREEMENTS.'},
    ('PlantComponent:UserDefined', 'Plant_Connection_1_Loop_Flow_Request_Mode'): {
        'NeedsFlowIfLoopOn': 'requests flow only if the loop is already running',
        'NeedsFlowAndTurnsLoopOn': 'requests flow and can start the loop running',
        'ReceivesWhateverFlowAvailable': 'takes whatever flow the loop provides, neither requests nor starts it'},
    ('Coil:UserDefined', 'Plant_Connection_is_Used'): {
        'Yes': 'Plant Connection Inlet/Outlet Node Name are read and connected', 'No': 'coil has no plant-side connection; those node fields are ignored'},

    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Heating_Limit'): {
        'NoLimit': 'no limit on heating air flow or capacity (Maximum Heating Air Flow Rate / Maximum Sensible Heating Capacity ignored)',
        'LimitFlowRate': 'caps heating air flow via Maximum Heating Air Flow Rate',
        'LimitCapacity': 'caps heating capacity via Maximum Sensible Heating Capacity',
        'LimitFlowRateAndCapacity': 'both limits apply'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Cooling_Limit'): {
        'NoLimit': 'no limit on cooling air flow or capacity',
        'LimitFlowRate': 'caps cooling air flow via Maximum Cooling Air Flow Rate',
        'LimitCapacity': 'caps cooling capacity via Maximum Total Cooling Capacity',
        'LimitFlowRateAndCapacity': 'both limits apply'},
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Outdoor_Air_Method'): {
        'None': 'no outdoor air; all outdoor-air-related fields ignored',
        'Flow/Person': 'uses Outdoor Air Flow Rate per Person', 'Flow/Zone': 'uses Outdoor Air Flow Rate per Zone',
        'Flow/Area': 'uses Outdoor Air Flow Rate per Zone Floor Area', 'Sum': 'sums the per-person/per-area/per-zone flow fields',
        'Maximum': 'takes the maximum of the per-person/per-area/per-zone flow fields',
        'DetailedSpecification': 'ignores the three Outdoor Air Flow Rate fields; uses Design Specification Outdoor Air Object Name and Design Specification Zone Air Distribution Object Name instead',
        'note': 'Same key set and gating pattern recurs (without the None key, and with the field itself required) on every other HVACTemplate:Zone:* and HVACTemplate:System:* object that has an Outdoor Air Method field.'},
    ('HVACTemplate:Zone:VAV', 'Zone_Minimum_Air_Flow_Input_Method'): {
        'Constant': 'minimum flow fraction fixed at Constant Minimum Air Flow Fraction',
        'FixedFlowRate': 'minimum flow fixed at Fixed Minimum Air Flow Rate',
        'Scheduled': 'minimum flow fraction follows Minimum Air Flow Fraction Schedule Name (Constant/Fixed fields become optional sizing hints only)'},
    ('HVACTemplate:Zone:VAV', 'Zone_Cooling_Design_Supply_Air_Temperature_Input_Method'): {
        'SupplyAirTemperature': 'uses the fixed Cooling Coil Design Setpoint value',
        'TemperatureDifference': 'uses Zone Cooling Design Supply Air Temperature Difference subtracted from zone peak temperature'},
    ('HVACTemplate:Zone:VAV', 'Zone_Heating_Design_Supply_Air_Temperature_Input_Method'): {
        'SupplyAirTemperature': 'uses the fixed Heating Coil Design Setpoint value',
        'TemperatureDifference': 'uses Zone Heating Design Supply Air Temperature Difference added to zone peak temperature'},
    ('HVACTemplate:System:VAV', 'Economizer_Type'): {
        'NoEconomizer': 'no economizer; economizer limit fields have no effect',
        'FixedDryBulb': 'Economizer Upper/Lower Temperature Limit apply', 'FixedEnthalpy': 'Economizer Upper Enthalpy Limit applies',
        'DifferentialDryBulb': 'compares outdoor to return air dry-bulb, no fixed limit fields needed',
        'DifferentialEnthalpy': 'compares outdoor to return air enthalpy',
        'FixedDewPointAndDryBulb': 'Economizer Maximum Limit Dewpoint Temperature applies (in addition to dry-bulb limits)',
        'ElectronicEnthalpy': 'uses a variable enthalpy curve', 'DifferentialDryBulbAndEnthalpy': 'combines the two differential tests'},
    ('HVACTemplate:System:VAV', 'Night_Cycle_Control'): {
        'StayOff': 'system stays off outside occupied hours regardless of zone conditions',
        'CycleOnAny': 'system cycles on if any zone needs conditioning', 'CycleOnControlZone': 'system cycles on based on Night Cycle Control Zone Name only',
        'CycleOnAnyZoneFansOnly': 'like CycleOnAny but only zone fans (not the central system) cycle on'},
    ('HVACTemplate:Zone:Unitary', 'Condenser_Type'): {
        'AirCooled': 'no condenser water/pump fields used', 'WaterCooled': 'uses Water Condenser Volume Flow Rate',
        'EvaporativelyCooled': 'uses Evaporative Condenser Air Flow Rate / Effectiveness / Pump Rated Power Consumption and enables Basin Heater fields'},
    ('HVACTemplate:Zone:Unitary', 'Defrost_Strategy'): {
        'ReverseCycle': 'defrost by briefly reversing the refrigeration cycle', 'Resistive': 'defrost via Resistive Defrost Heater Capacity'},
    ('HVACTemplate:Zone:Unitary', 'Defrost_Control'): {
        'Timed': 'uses a fixed Defrost Time Period Fraction', 'OnDemand': 'defrosts only when frost accumulation warrants it'},
    ('HVACTemplate:Plant:Chiller', 'Chiller_Type'): {
        'DistrictChilledWater': 'purchased chilled water; Nominal COP and Condenser Type are not applicable',
        'ElectricCentrifugalChiller': 'maps to Chiller:Electric with centrifugal performance curves',
        'ElectricScrewChiller': 'maps to Chiller:Electric with screw-compressor performance curves',
        'ElectricReciprocatingChiller': 'maps to Chiller:Electric with reciprocating-compressor performance curves'},
}

AUTOSIZABLE = {
    # Electric Load Center / Generators -- none. No \autosizable or \autocalculatable
    # field exists anywhere in the Electric Load Center-Generator IDD group.

    # HVAC Template Objects -- every \autosizable field found in the group
    # (field name recurs across most of the ~30 HVACTemplate:Zone/System/Plant
    # objects that have that kind of field; object column names one
    # representative object per field).
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Heating_Air_Flow_Rate'),
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Sensible_Heating_Capacity'),
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Cooling_Air_Flow_Rate'),
    ('HVACTemplate:Zone:IdealLoadsAirSystem', 'Maximum_Total_Cooling_Capacity'),
    ('HVACTemplate:Zone:BaseboardHeat', 'Baseboard_Heating_Capacity'),
    ('HVACTemplate:Zone:FanCoil', 'Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:FanCoil', 'Cooling_Coil_Design_Setpoint'),
    ('HVACTemplate:Zone:FanCoil', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:Zone:FanCoil', 'Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:Zone:FanCoil', 'Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:FanCoil', 'Baseboard_Heating_Capacity'),
    ('HVACTemplate:Zone:PTAC', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:PTAC', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:Zone:PTAC', 'Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:Zone:PTAC', 'Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:PTAC', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:PTAC', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:PTAC', 'Supplemental_Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:PTAC', 'Baseboard_Heating_Capacity'),
    ('HVACTemplate:Zone:PTHP', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:PTHP', 'Heat_Pump_Heating_Coil_Gross_Rated_Capacity'),
    ('HVACTemplate:Zone:PTHP', 'DX_Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:Zone:PTHP', 'DX_Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:Zone:PTHP', 'Supplemental_Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:PTHP', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:PTHP', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:PTHP', 'Baseboard_Heating_Capacity'),
    ('HVACTemplate:Zone:PTHP', 'Resistive_Defrost_Heater_Capacity'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Supplemental_Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:WaterToAirHeatPump', 'Baseboard_Heating_Capacity'),
    ('HVACTemplate:Zone:Unitary', 'Heating_Coil_Capacity'),
    ('HVACTemplate:Zone:Unitary', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:Unitary', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:Zone:Unitary', 'Resistive_Defrost_Heater_Capacity'),
    ('HVACTemplate:Zone:Unitary', 'Water_Condenser_Volume_Flow_Rate'),
    ('HVACTemplate:Zone:Unitary', 'Evaporative_Condenser_Air_Flow_Rate'),
    ('HVACTemplate:Zone:Unitary', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('HVACTemplate:Zone:VAV', 'Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:VAV', 'Primary_Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:VAV', 'Primary_Supply_Air_Minimum_Flow_Fraction'),
    ('HVACTemplate:Zone:VAV', 'Supplemental_Heating_or_Reheat_Coil_Capacity'),
    ('HVACTemplate:Zone:VAV:FanPowered', 'Cold_Duct_Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:VAV:FanPowered', 'Hot_Duct_Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:VAV:FanPowered', 'Main_Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:VAV:FanPowered', 'Parallel_Fan_On_Flow_Fraction'),
    ('HVACTemplate:Zone:VAV:HeatAndCool', 'Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:ConstantVolume', 'Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:DualDuct', 'Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:Zone:DualDuct', 'Secondary_Supply_Air_Maximum_Flow_Rate'),
    ('HVACTemplate:System:Unitary', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:Unitary', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:System:Unitary', 'Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:System:Unitary', 'Heating_Coil_Capacity'),
    ('HVACTemplate:System:Unitary', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:Unitary', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Heating_Coil_Capacity'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Cooling_Coil_Gross_Rated_Sensible_Heat_Ratio'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Supplemental_Heating_Coil_Capacity'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:UnitaryHeatPump:AirToAir', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:UnitarySystem', 'Cooling_Design_Supply_Air_Flow_Rate'),
    ('HVACTemplate:System:UnitarySystem', 'Heating_Design_Supply_Air_Flow_Rate'),
    ('HVACTemplate:System:VAV', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:VAV', 'Supply_Fan_Minimum_Flow_Rate'),
    ('HVACTemplate:System:VAV', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:VAV', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:VAV', 'Humidifier_Rated_Electric_Power'),
    ('HVACTemplate:System:PackagedVAV', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:PackagedVAV', 'Supply_Fan_Minimum_Flow_Rate'),
    ('HVACTemplate:System:PackagedVAV', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:System:PackagedVAV', 'Heating_Coil_Capacity'),
    ('HVACTemplate:System:PackagedVAV', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:PackagedVAV', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:ConstantVolume', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:ConstantVolume', 'Cooling_Coil_Design_Setpoint'),
    ('HVACTemplate:System:DualDuct', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:DualDuct', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:DualDuct', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('HVACTemplate:System:DedicatedOutdoorAir', 'Supply_Fan_Maximum_Flow_Rate'),
    ('HVACTemplate:System:DedicatedOutdoorAir', 'Cooling_Coil_Gross_Rated_Total_Capacity'),
    ('HVACTemplate:System:DedicatedOutdoorAir', 'Heating_Coil_Capacity'),
    ('HVACTemplate:Plant:Chiller', 'Capacity'),
    ('HVACTemplate:Plant:Tower', 'High_Speed_Fan_Power'),
    ('HVACTemplate:Plant:Tower', 'Low_Speed_Fan_Power'),
    ('HVACTemplate:Plant:Boiler', 'Capacity'),
}

CONSTRAINTS = {
    'LoadProfile:Plant': [
        'Must be connected on the demand side of a plant loop, on a Branch with control type Active.',
        'Cooling loads are entered as negative numbers; positive values impose a heating load.',
        'The actual load-side flow rate is Peak Flow Rate multiplied by the current Flow Rate Fraction Schedule value.',
    ],
    'ElectricLoadCenter:Transformer': [
        'Phase is accepted by the IDD (keys 1 or 3) but its own \\note says "NOT used in the current model" -- changing it has no simulated effect.',
        'Only one PowerInFromGrid transformer and one PowerOutToGrid transformer are recommended per model.',
        'Meter <n> Name entries must reference an electricity-resource-type meter; typically discovered from the .mdd file after an initial run.',
    ],
    'ElectricLoadCenter:Distribution': [
        'Generator Operation Scheme Type is only meaningful if Generator List Name is entered.',
        'Storage Converter Object Name is expected (for charging DC storage from the grid) specifically under the FacilityDemandLeveling and TrackChargeDischargeSchedules storage operation schemes.',
        'Transformer Object Name is only needed when power must be exported from on-site generation/storage to the grid through a transformer.',
    ],
    'ElectricLoadCenter:Generators': [
        'A given ElectricLoadCenter:Generators list can be referenced by only one ElectricLoadCenter:Distribution object.',
        'Generator <n> Object Type must be one of: Generator:InternalCombustionEngine, Generator:CombustionTurbine, Generator:Photovoltaic, Generator:PVWatts, Generator:FuelCell, Generator:MicroCHP, Generator:MicroTurbine, Generator:WindTurbine.',
    ],
    'ElectricLoadCenter:Inverter:PVWatts': [
        'Not compatible with other Generator objects such as Generator:Photovoltaic; intended for use with one or more Generator:PVWatts objects on the same load center.',
    ],
    'Generator:FuelCell:AuxiliaryHeater': [
        'IDD memo: "this portion of the model is not yet available" -- the object is required for input-file completeness (so internal data structures can be allocated) but its field values (Excess Air Ratio, Ancillary Power terms, Skin Loss U-Factor Times Area Value, Heating Capacity fields) are not used by the simulation. This is a purpose-built example of fields that produce zero response no matter what value a student enters.',
    ],
    'Generator:Photovoltaic': [
        'Module Performance Name must reference a PhotovoltaicPerformance:* object whose object type matches Photovoltaic Performance Object Type.',
        'Array tilt, azimuth and gross area are taken from the referenced Surface Name, not entered directly on this object.',
    ],
    'Generator:PVWatts': [
        'Ground Coverage Ratio only affects arrays with one-axis tracking (Array Type = OneAxis or OneAxisBacktracking).',
    ],
    'Generator:WindTurbine': [
        'Power Coefficient C1-C6 (the analytic approximation for Horizontal Axis Wind Turbines) are only used as a set; per the IDD note, if any one of C1-C6 is left blank the program falls back to the simple approximation for all six.',
        'Blade Drag Coefficient and Blade Lift Coefficient are documented as required specifically for Vertical Axis Wind Turbine and have no role for Horizontal Axis Wind Turbine.',
    ],
    'FaultModel:Fouling:Coil': [
        'Coil Name must reference an existing simple water heating or cooling coil object.',
    ],
    'FaultModel:HumidistatOffset': [
        'Humidistat Name must reference a ZoneControl:Humidistat object.',
        'Related Thermostat Offset Fault Name, when used, must reference a FaultModel:ThermostatOffset object.',
    ],
    'FaultModel:ThermostatOffset': [
        'Thermostat Name must reference a ZoneControl:Thermostat object.',
    ],
    'FaultModel:Fouling:AirFilter': [
        'Fan Name must reference an existing fan object whose type matches Fan Object Type (Fan:OnOff, Fan:ConstantVolume or Fan:VariableVolume in this IDD version; the IDD notes Fan:SystemModel support is pending).',
        'Fan Curve Name must reference a curve covering the fan\'s design operating point (pressure rise vs. air flow).',
    ],
    'FaultModel:Fouling:Boiler': [
        'Boiler Object Type accepts only Boiler:HotWater in this IDD version (the fault applies to water-based hot-water boilers).',
        'Boiler Object Name must reference an existing Boiler:HotWater object.',
    ],
    'FaultModel:Fouling:Chiller': [
        'Chiller Object Type is restricted to water-cooled-condenser chiller types: Chiller:Electric, Chiller:Electric:EIR, Chiller:Electric:ReformulatedEIR, Chiller:ConstantCOP, Chiller:EngineDriven, Chiller:CombustionTurbine.',
        'Chiller Object Name must reference an existing chiller of that type.',
    ],
    'FaultModel:Fouling:CoolingTower': [
        'Cooling Tower Object Type is restricted to CoolingTower:SingleSpeed, CoolingTower:TwoSpeed or CoolingTower:VariableSpeed:MERKEL in this IDD version (narrower than the sensor-offset fault, which also allows plain CoolingTower:VariableSpeed).',
        'Reference UA Reduction Factor applies to both the Design UA and Free Convection UA of the tower.',
    ],
    'FaultModel:Fouling:EvaporativeCooler': [
        'Evaporative Cooler Object Type accepts only EvaporativeCooler:Indirect:WetCoil (the fault does not apply to direct evaporative coolers or dry-coil indirect coolers).',
        'The IDD\'s object-list for Evaporative Cooler Object Name is "Chillers" -- an apparent copy-paste error in Energy+.idd (see IDD_DISAGREEMENTS); the field is documented to hold the name of the EvaporativeCooler:Indirect:WetCoil object.',
    ],
    'FaultModel:TemperatureSensorOffset:ChillerSupplyWater': [
        'Chiller Object Name must reference an existing chiller of the type given in Chiller Object Type (any of the eight listed chiller types, including absorption).',
    ],
    'FaultModel:TemperatureSensorOffset:CondenserSupplyWater': [
        'Cooling Tower Object Name must reference an existing cooling tower of the type given in Cooling Tower Object Type.',
    ],
    'FaultModel:TemperatureSensorOffset:CoilSupplyAir': [
        'Coil Object Name must reference an existing object of the type given in Coil Object Type (includes AirLoopHVAC:UnitarySystem, CoilSystem:Cooling:DX and CoilSystem:Heating:DX in addition to the plain Coil:* types).',
        'Water Coil Controller Name is required only when Coil Object Type is one of the water coils (Coil:Heating:Water, Coil:Cooling:Water, Coil:Cooling:Water:Detailedgeometry).',
    ],
    'Curve (all Curve:* objects)': [
        'Every curve object clamps its independent variable(s) to [Minimum Value of x/w/y/z/v, Maximum Value of x/w/y/z/v] before evaluating the polynomial: values outside that range are replaced by the nearest bound. A coefficient change that only affects the curve\'s behavior outside the min/max window is therefore invisible in any simulation result -- the student sees a flat response.',
        'Every curve object also clamps its result to the optional [Minimum Curve Output, Maximum Curve Output] fields, when entered: if the whole operating range maps into a value outside those bounds, changing the coefficients further has no visible effect once the clamp is active.',
        'Curve:Functional:PressureDrop has no Minimum/Maximum Curve Output fields (it outputs a pressure drop from a fixed physical formula, not a fitted polynomial) and no independent-variable min/max fields either -- none of the curve/table clamping constraints above apply to it.',
    ],
    'Table:Lookup': [
        'Minimum Output / Maximum Output clamp the (non-normalized) result the same way Minimum/Maximum Curve Output do for Curve:* objects.',
        'Normalization Divisor is only meaningful when Normalization Method is DivisorOnly or AutomaticWithDivisor; under None it has no effect.',
        'External File Name, when given, supplies the Output Value data and the in-object Output Value <n> fields are not read; Normalization Reference Value still comes from the associated Table:IndependentVariable objects either way.',
    ],
    'Table:IndependentVariable': [
        'Minimum Value / Maximum Value bound the domain; outside that range the Extrapolation Method (Constant or Linear) governs the result instead of the Value <n> data, and EnergyPlus issues a warning.',
        'Values (whether from Value <n> fields or an External File) must be listed in ascending order or EnergyPlus raises an error.',
        'If Normalization Reference Value is left blank on one Table:IndependentVariable object, it must be left blank on every other Table:IndependentVariable object referenced by the same Table:IndependentVariableList.',
    ],
    'FluidProperties (all FluidProperties:* objects)': [
        'A fluid used anywhere in FluidProperties:GlycolConcentration/Saturated/Superheated/Concentration must first be declared in a FluidProperties:Name object with a matching Fluid Type (Refrigerant or Glycol).',
        'Glycol Concentration must be between 0.0 and 1.0.',
        'The count of property values entered in FluidProperties:Saturated/Superheated/Concentration must match the count of temperatures in the referenced FluidProperties:Temperatures list (one-to-one correspondence), and temperatures are assumed to be listed in ascending order.',
    ],
    'HybridModel:Zone': [
        'Only one of Calculate Zone Internal Thermal Mass, Calculate Zone Air Infiltration Rate, and Calculate Zone People Count may be Yes at a time (per the IDD notes on the Air Infiltration Rate and People Count fields); setting a later one to Yes effectively disables the earlier one\'s inverse calculation.',
        'When Calculate Zone Air Infiltration Rate or Calculate Zone People Count is Yes, the measured-data schedules must be supplied in one of the documented combinations (free-floating: one of temperature/humidity-ratio/CO2; HVAC-on: that measurement plus Zone Input Supply Air Mass Flow Rate Schedule Name and the matching Zone Input Supply Air <property> Schedule Name).',
        'A Schedule:File used for the measured data must cover a full year, with zeros outside the Begin/End Month/Day range.',
    ],
    'PlantComponent:UserDefined': [
        'Must appear directly on a Branch object.',
        'All referenced *Program Calling Manager Name fields must name existing EnergyManagementSystem:ProgramCallingManager objects using the calling point "UserDefinedComponentModel".',
        'Number of Plant Loop Connections is limited to 1-4; only that many Plant Connection <n> node/loading-mode/flow-mode/program-manager field sets are active.',
    ],
    'Coil:UserDefined': [
        'Must appear on a Branch object or in an AirLoopHVAC:OutdoorAirSystem:EquipmentList.',
        'Number of Air Connections is limited to 1-2; Air Connection 2 node names are only meaningful when it is 2.',
    ],
    'ZoneHVAC:ForcedAir:UserDefined': [
        'Primary Air Inlet Node Name must be a zone air exhaust node; Primary Air Outlet Node Name must be a zone air inlet node (both per ZoneHVAC:EquipmentConnections).',
        'Number of Plant Loop Connections is limited to 0-3.',
    ],
    'AirTerminal:SingleDuct:UserDefined': [
        'Primary Air Inlet Node Name must be a zone splitter outlet node; Primary Air Outlet Node Name must be a zone air inlet node.',
        'Number of Plant Loop Connections is limited to 0-2.',
    ],
    'PlantEquipmentOperation:UserDefined': [
        'Must be referenced by a PlantEquipmentOperationSchemes or CondenserEquipmentOperationSchemes object to have any effect.',
        'Up to 10 Equipment <n> Object Type/Name pairs may be listed; each must reference existing plant/condenser equipment.',
    ],
    'PythonPlugin:TrendVariable': [
        'Name of a Python Plugin Variable must reference a variable already declared in a PythonPlugin:Variables object.',
    ],
    'PythonPlugin:OutputVariable': [
        'Python Plugin Variable Name must be listed in a PythonPlugin:Variables object.',
        'Type of Data in Variable = Metered is automatically treated as Summed internally.',
    ],
    'PythonPlugin:Instance': [
        'Plugin Class Name must name a class that inherits the EnergyPlusPlugin base class, defined in the Python file named by Python Module Name (without the .py extension); the simulation aborts otherwise.',
        'Python Module Name is resolved by searching the plugin search path (executable directory, current working directory, input file directory, and any paths added via PythonPlugin:SearchPaths).',
    ],
    'HVACTemplate (general)': [
        'HVACTemplate:* objects are not read directly by the EnergyPlus simulation engine; per the reference\'s processing page, a preprocessing step (ExpandObjects) expands them into ordinary IDF objects before the simulation runs. A platform that edits HVACTemplate fields must re-run that expansion for the change to reach the simulation.',
    ],
    'HVACTemplate:Zone:IdealLoadsAirSystem': [
        'Maximum Cooling Air Flow Rate is required whenever Outdoor Air Economizer Type is anything other than NoEconomizer, independent of the Cooling Limit setting.',
    ],
    'HVACTemplate:Plant:Chiller': [
        'Nominal COP and Condenser Type are not applicable when Chiller Type = DistrictChilledWater, even though Nominal COP is marked \\required-field in the IDD (see IDD_DISAGREEMENTS).',
    ],
}

SECTIONS_READ = [
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-non-zone-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-electric-load-center-generator.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-operational-faults.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-performance-curves.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-performance-tables.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-fluid-properties.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-hybrid-model.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-user-defined-hvac-and-plant-component.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-python-plugins.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/hvac-template-objects.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/hvactemplate-processing.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-hvac-templates.html',
]

IDD_DISAGREEMENTS = [
    'Generator:FuelCell:PowerModule "Nominal Efficiency" and "Nominal Electrical Power" carry IDD notes "This field is not used." / "This field is not used" respectively, even though the BigLadder prose describes them as the inputs used under Efficiency Curve Mode = Normalized.',
    'Generator:FuelCell:ExhaustGasToWaterHeatExchanger field N15 is named "Method 3 Water Area" in Energy+.idd; the BigLadder prose calls it "Method 3 Area Water Coefficient".',
    'PlantComponent:UserDefined uses inconsistent choice-key spelling for Plant Connection Loading Mode across connections: connection 1 uses "MeetsLoadWith..." (DemandsLoad, MeetsLoadWithPassiveCapacity, MeetsLoadWithNominalCapacity, MeetsLoadWithNominalCapacityLowOutLimit, MeetsLoadWithNominalCapacityHiOutLimit) while connections 2-4 use "MeetLoadWith..." (missing the "s") for the equivalent keys -- confirmed in Energy+.idd; prose treats them as identical.',
    'PythonPlugin:Instance is singular in Energy+.idd ("PythonPlugin:Instance"), not "PythonPlugin:Instances" as sometimes referenced in prose/section descriptions.',
    'FaultModel:TemperatureSensorOffset:CoilSupplyAir "Coil Object Type" in Energy+.idd includes AirLoopHVAC:UnitarySystem, CoilSystem:Cooling:DX and CoilSystem:Heating:DX in addition to the plain Coil:Heating/Cooling:* keys, and spells the detailed-geometry key "Coil:Cooling:Water:Detailedgeometry" (lowercase "g"); prose summaries commonly omit the CoilSystem keys and capitalize "DetailedGeometry".',
    'FaultModel:Fouling:EvaporativeCooler field A5 ("Evaporative Cooler Object Name") is tagged with \\object-list Chillers in Energy+.idd -- almost certainly a copy-paste artifact, since the field is documented to hold the name of an EvaporativeCooler:Indirect:WetCoil object, not a chiller.',
    'HVACTemplate:Plant:Chiller "Nominal COP" is marked \\required-field in Energy+.idd even though its own IDD \\note says it is "Not applicable if Chiller Type is DistrictChilledWater".',
    'Group - Non-Zone Equipment contains only LoadProfile:Plant in this IDD/doc version (confirmed via the IDD\'s "\\group Non-Zone Equipment" tag and the BigLadder page\'s single object section); it does not include WaterUse:*, GroundHeatExchanger:*, District*, or other objects one might expect from the group name.',
]
