"""Rules from: Group - Unitary Equipment; Group - Variable Refrigerant Flow Equipment;
Group - Radiative/Convective Units; Group Heating and Cooling Coils; Group - Fans;
Group - Humidifiers and Dehumidifiers; Group Evaporative Coolers; Group Heat Recovery;
Group - Refrigeration.
(EnergyPlus 9.6 Input Output Reference, bigladdersoftware.com/epx/docs/9-6/input-output-reference/)

All class and field names verified against C:/EnergyPlusV9-6-0/Energy+.idd. Where the web
prose and the IDD disagreed, the IDD field/key spelling was used and the disagreement logged
in IDD_DISAGREEMENTS below. AUTOSIZABLE was built by scanning the IDD directly for the
\\autosizable and \\autocalculatable markers (more reliable than the prose), not by transcribing
the HTML page.
"""

GATED = {
    # --- AirLoopHVAC:UnitarySystem ---
    ('AirLoopHVAC:UnitarySystem', 'Reheat_Coil_Object_Type'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},
    ('AirLoopHVAC:UnitarySystem', 'Reheat_Coil_Name'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},
    ('AirLoopHVAC:UnitarySystem', 'Controlling_Zone_or_Thermostat_Location'): {
        'by': 'Control_Type', 'when': ('Load', 'SingleZoneVAV'), 'note': 'Not used for SetPoint control.'},
    ('AirLoopHVAC:UnitarySystem', 'Minimum_Supply_Air_Temperature'): {
        'by': 'Control_Type', 'when': ('SingleZoneVAV',),
        'note': "Also used when Use_DOAS_DX_Cooling_Coil = Yes; in that combination it is not autosizable and capped at 7.5C."},
    ('AirLoopHVAC:UnitarySystem', 'Design_Specification_Multispeed_Object_Type'): {
        'by': 'Heating_Coil_Object_Type', 'when': ('Coil:Heating:DX:MultiSpeed', 'Coil:Cooling:DX:MultiSpeed', 'Coil:Heating:Gas:MultiStage', 'Coil:Heating:Electric:MultiStage'),
        'note': 'Required only when a multispeed/multistage coil is used; see UnitarySystemPerformance:Multispeed.'},
    ('AirLoopHVAC:UnitarySystem', 'Design_Specification_Multispeed_Object_Name'): {
        'by': 'Heating_Coil_Object_Type', 'when': ('Coil:Heating:DX:MultiSpeed', 'Coil:Cooling:DX:MultiSpeed', 'Coil:Heating:Gas:MultiStage', 'Coil:Heating:Electric:MultiStage'),
        'note': 'Required only when a multispeed/multistage coil is used.'},
    # --- AirLoopHVAC:Unitary:Furnace:HeatCool / UnitaryHeatCool ---
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'Reheat_Coil_Object_Type'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'Reheat_Coil_Name'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},
    ('AirLoopHVAC:UnitaryHeatCool', 'Reheat_Coil_Object_Type'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},
    ('AirLoopHVAC:UnitaryHeatCool', 'Reheat_Coil_Name'): {
        'by': 'Dehumidification_Control_Type', 'when': ('CoolReheat',), 'note': 'Required only for CoolReheat dehumidification.'},

    # --- AirConditioner:VariableRefrigerantFlow ---
    ('AirConditioner:VariableRefrigerantFlow', 'Evaporative_Condenser_Effectiveness'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'IDD note ties this explicitly to EvaporativelyCooled.'},
    ('AirConditioner:VariableRefrigerantFlow', 'Evaporative_Condenser_Air_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Also only relevant while Basin_Heater_Operating_Schedule_Name says the heater is available.'},
    ('AirConditioner:VariableRefrigerantFlow', 'Basin_Heater_Setpoint_Temperature'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Basin_Heater_Operating_Schedule_Name'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Condenser_Outlet_Node_Name'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',), 'note': 'Leave blank if Condenser_Type is AirCooled or EvaporativelyCooled.'},
    ('AirConditioner:VariableRefrigerantFlow', 'Water_Condenser_Volume_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Thermostat_Priority_Schedule_Name'): {
        'by': 'Master_Thermostat_Priority_Control_Type', 'when': ('Scheduled',), 'note': 'Required only when priority control type is Scheduled.'},
    ('AirConditioner:VariableRefrigerantFlow', 'Resistive_Defrost_Heater_Capacity'): {
        'by': 'Defrost_Strategy', 'when': ('Resistive',), 'note': "IDD key is 'Resistive' (not 'ReverseCycle')."},
    ('AirConditioner:VariableRefrigerantFlow', 'Defrost_Energy_Input_Ratio_Modifier_Function_of_Temperature_Curve_Name'): {
        'by': 'Defrost_Strategy', 'when': ('ReverseCycle',), 'note': "IDD key is 'ReverseCycle', not 'reverse-cycle' as an initial web summary spelled it."},
    ('AirConditioner:VariableRefrigerantFlow', 'Minimum_Condenser_Inlet_Node_Temperature_in_Heat_Recovery_Mode'): {
        'by': 'Heat_Pump_Waste_Heat_Recovery', 'when': ('Yes',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Maximum_Condenser_Inlet_Node_Temperature_in_Heat_Recovery_Mode'): {
        'by': 'Heat_Pump_Waste_Heat_Recovery', 'when': ('Yes',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Heat_Recovery_Cooling_Capacity_Modifier_Curve_Name'): {
        'by': 'Heat_Pump_Waste_Heat_Recovery', 'when': ('Yes',), 'note': None},
    ('AirConditioner:VariableRefrigerantFlow', 'Heat_Recovery_Heating_Capacity_Modifier_Curve_Name'): {
        'by': 'Heat_Pump_Waste_Heat_Recovery', 'when': ('Yes',), 'note': None},

    # --- Radiative/Convective Units: 'Design Object' indirection (9.4+ split) ---
    # NOTE: in this IDD, ZoneHVAC:Baseboard:RadiantConvective:Water, :Steam,
    # ZoneHVAC:LowTemperatureRadiant:VariableFlow and :ConstantFlow do NOT carry the
    # Heating/Cooling Design Capacity Method fields themselves any more -- those live on
    # a companion "...:Design" object referenced by the "Design Object" field. An initial
    # web summary attributed the Method fields directly to the parent objects; see
    # IDD_DISAGREEMENTS.
    ('ZoneHVAC:Baseboard:RadiantConvective:Water:Design', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:Baseboard:RadiantConvective:Water:Design', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:Baseboard:RadiantConvective:Steam:Design', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:Baseboard:RadiantConvective:Steam:Design', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:Baseboard:RadiantConvective:Electric', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:Baseboard:RadiantConvective:Electric', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:Baseboard:Convective:Water', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:Baseboard:Convective:Water', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:Baseboard:Convective:Electric', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:Baseboard:Convective:Electric', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Cooling_Design_Capacity_Per_Floor_Area'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow:Design', 'Fraction_of_Autosized_Cooling_Design_Capacity'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('FractionOfAutosizedCoolingCapacity',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:Electric', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:LowTemperatureRadiant:Electric', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:HighTemperatureRadiant', 'Heating_Design_Capacity_Per_Floor_Area'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:HighTemperatureRadiant', 'Fraction_of_Autosized_Heating_Design_Capacity'): {
        'by': 'Heating_Design_Capacity_Method', 'when': ('FractionOfAutosizedHeatingCapacity',), 'note': None},
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Design_Capacity_Per_Floor_Area'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('CapacityPerFloorArea',), 'note': None},
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Fraction_of_Autosized_Cooling_Design_Capacity'): {
        'by': 'Cooling_Design_Capacity_Method', 'when': ('FractionOfAutosizedCoolingCapacity',), 'note': None},
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Control_Throttling_Range'): {
        'by': 'Control_Type', 'when': ('MeanAirTemperature', 'MeanRadiantTemperature', 'OperativeTemperature', 'OutdoorDryBulbTemperature', 'OutdoorWetBulbTemperature'),
        'note': 'Not used when Control_Type is ZoneTotalLoad or ZoneConvectiveLoad.'},
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Control_Temperature_Schedule_Name'): {
        'by': 'Control_Type', 'when': ('MeanAirTemperature', 'MeanRadiantTemperature', 'OperativeTemperature', 'OutdoorDryBulbTemperature', 'OutdoorWetBulbTemperature'),
        'note': 'Not used when Control_Type is ZoneTotalLoad or ZoneConvectiveLoad.'},
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Condensation_Control_Dewpoint_Offset'): {
        'by': 'Condensation_Control_Type', 'when': ('SimpleOff', 'VariableOff'), 'note': 'Not used when Condensation_Control_Type = Off.'},

    # --- Coil:Heating:Water ---
    ('Coil:Heating:Water', 'U_Factor_Times_Area_Value'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',), 'note': None},
    ('Coil:Heating:Water', 'Maximum_Water_Flow_Rate'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',), 'note': None},
    ('Coil:Heating:Water', 'Rated_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': "IDD field name is 'Rated Capacity', not 'Gross Rated Heating Capacity'."},
    ('Coil:Heating:Water', 'Rated_Inlet_Water_Temperature'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': 'Ignored during UA/flow-rate sizing.'},
    ('Coil:Heating:Water', 'Rated_Inlet_Air_Temperature'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': None},
    ('Coil:Heating:Water', 'Rated_Outlet_Water_Temperature'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': None},
    ('Coil:Heating:Water', 'Rated_Outlet_Air_Temperature'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': None},

    # --- Fan:SystemModel ---
    ('Fan:SystemModel', 'Electric_Power_Function_of_Flow_Fraction_Curve_Name'): {
        'by': 'Speed_Control_Method', 'when': ('Continuous',), 'note': 'Also required if Number_of_Speeds > 1 and per-speed power fractions are not used.'},
    ('Fan:SystemModel', 'Electric_Power_Per_Unit_Flow_Rate'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlow',), 'note': None},
    ('Fan:SystemModel', 'Electric_Power_Per_Unit_Flow_Rate_Per_Unit_Pressure'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlowPerPressure',), 'note': None},
    ('Fan:SystemModel', 'Fan_Total_Efficiency'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('TotalEfficiencyAndPressure',), 'note': None},
    ('Fan:SystemModel', 'Motor_Loss_Radiative_Fraction'): {
        'by': 'Motor_Loss_Zone_Name', 'when': ('<any zone name>',), 'note': 'Only meaningful once a Motor_Loss_Zone_Name is specified.'},

    # --- Fan:VariableVolume ---
    ('Fan:VariableVolume', 'Fan_Power_Minimum_Flow_Fraction'): {
        'by': 'Fan_Power_Minimum_Flow_Rate_Input_Method', 'when': ('Fraction',), 'note': None},
    ('Fan:VariableVolume', 'Fan_Power_Minimum_Air_Flow_Rate'): {
        'by': 'Fan_Power_Minimum_Flow_Rate_Input_Method', 'when': ('FixedFlowRate',), 'note': None},

    # --- Humidifier:Steam:Gas ---
    ('Humidifier:Steam:Gas', 'Thermal_Efficiency'): {
        'by': 'Inlet_Water_Temperature_Option', 'when': ('FixedInletWaterTemperature',),
        'note': 'Ignored (ineffective) if Rated_Gas_Use_Rate is hard-sized and this option is FixedInletWaterTemperature; also ignored (internally computed) if VariableInletWaterTemperature is selected.'},

    # --- Dehumidifier:Desiccant:NoFans ---
    ('Dehumidifier:Desiccant:NoFans', 'Leaving_Maximum_Humidity_Ratio_Setpoint'): {
        'by': 'Control_Type', 'when': ('LeavingMaximumHumidityRatioSetpoint',), 'note': None},
    ('Dehumidifier:Desiccant:NoFans', 'Leaving_Dry_Bulb_Function_of_Entering_Dry_Bulb_and_Humidity_Ratio_Curve_Name'): {
        'by': 'Performance_Model_Type', 'when': ('UserCurves',), 'note': 'All eight UserCurves curve-name fields and Nominal_Regeneration_Temperature are only used when Performance_Model_Type = UserCurves; ignored (Default correlation used) otherwise.'},
    ('Dehumidifier:Desiccant:NoFans', 'Nominal_Regeneration_Temperature'): {
        'by': 'Performance_Model_Type', 'when': ('UserCurves',), 'note': 'Not used if Default is chosen for Performance_Model_Type.'},

    # --- HeatExchanger:AirToAir:SensibleAndLatent ---
    ('HeatExchanger:AirToAir:SensibleAndLatent', 'Initial_Defrost_Time_Fraction'): {
        'by': 'Frost_Control_Type', 'when': ('ExhaustAirRecirculation', 'ExhaustOnly'), 'note': 'Not used for None or MinimumExhaustTemperature frost control.'},
    ('HeatExchanger:AirToAir:SensibleAndLatent', 'Rate_of_Defrost_Time_Fraction_Increase'): {
        'by': 'Frost_Control_Type', 'when': ('ExhaustAirRecirculation', 'ExhaustOnly'), 'note': 'Not used for None or MinimumExhaustTemperature frost control.'},
    ('HeatExchanger:AirToAir:SensibleAndLatent', 'Threshold_Temperature'): {
        'by': 'Frost_Control_Type', 'when': ('ExhaustAirRecirculation', 'ExhaustOnly', 'MinimumExhaustTemperature'), 'note': 'Not used when Frost_Control_Type = None.'},

    # --- Refrigeration:Case ---
    ('Refrigeration:Case', 'Humidity_at_Zero_Anti_Sweat_Heater_Energy'): {
        'by': 'Anti_Sweat_Heater_Control_Type', 'when': ('Linear',), 'note': None},
    ('Refrigeration:Case', 'Case_Height'): {
        'by': 'Anti_Sweat_Heater_Control_Type', 'when': ('HeatBalanceMethod',), 'note': None},
    ('Refrigeration:Case', 'Case_Defrost_Schedule_Name'): {
        'by': 'Case_Defrost_Type', 'when': ('OffCycle', 'HotGas', 'Electric', 'HotFluid', 'HotGasWithTemperatureTermination', 'ElectricWithTemperatureTermination', 'HotFluidWithTemperatureTermination'),
        'note': 'Not used when Case_Defrost_Type = None.'},
    ('Refrigeration:Case', 'Defrost_Energy_Correction_Curve_Name'): {
        'by': 'Defrost_Energy_Correction_Curve_Type', 'when': ('CaseTemperatureMethod', 'RelativeHumidityMethod', 'DewpointMethod'),
        'note': 'Not used when Defrost_Energy_Correction_Curve_Type = None.'},

    # --- Refrigeration:CompressorRack ---
    ('Refrigeration:CompressorRack', 'Heat_Rejection_Zone_Name'): {
        'by': 'Heat_Rejection_Location', 'when': ('Zone',), 'note': None},
    ('Refrigeration:CompressorRack', 'Condenser_Air_Inlet_Node_Name'): {
        'by': 'Heat_Rejection_Location', 'when': ('Outdoors',), 'note': None},
    ('Refrigeration:CompressorRack', 'Water_Cooled_Condenser_Design_Flow_Rate'): {
        'by': 'Water_Cooled_Loop_Flow_Type', 'when': ('ConstantFlow',), 'note': "Only used when Condenser_Type = WaterCooled and this flow type is ConstantFlow."},
    ('Refrigeration:CompressorRack', 'Water_Cooled_Condenser_Outlet_Temperature_Schedule_Name'): {
        'by': 'Water_Cooled_Loop_Flow_Type', 'when': ('VariableFlow',), 'note': "Only used when Condenser_Type = WaterCooled and this flow type is VariableFlow."},
    ('Refrigeration:CompressorRack', 'Evaporative_Condenser_Air_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('Refrigeration:CompressorRack', 'Design_Evaporative_Condenser_Water_Pump_Power'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
    ('Refrigeration:CompressorRack', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': None},
}

METHOD_GROUPS = {
    # --- AirLoopHVAC:UnitarySystem: the three priority supply-air-flow-rate methods ---
    ('AirLoopHVAC:UnitarySystem', 'Cooling_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Cooling_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Cooling_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingValue': 'Cooling_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FlowPerCoolingCapacity': 'Cooling_Supply_Air_Flow_Rate_Per_Unit_of_Capacity',
    },
    ('AirLoopHVAC:UnitarySystem', 'Heating_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Heating_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Heating_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedHeatingValue': 'Heating_Fraction_of_Autosized_Heating_Supply_Air_Flow_Rate',
        'FlowPerHeatingCapacity': 'Heating_Supply_Air_Flow_Rate_Per_Unit_of_Capacity',
    },
    ('AirLoopHVAC:UnitarySystem', 'No_Load_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'No_Load_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'No_Load_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingValue': 'No_Load_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FractionOfAutosizedHeatingValue': 'No_Load_Fraction_of_Autosized_Heating_Supply_Air_Flow_Rate',
        'FlowPerCoolingCapacity': 'No_Load_Supply_Air_Flow_Rate_Per_Unit_of_Capacity_During_Cooling_Operation',
        'FlowPerHeatingCapacity': 'No_Load_Supply_Air_Flow_Rate_Per_Unit_of_Capacity_During_Heating_Operation',
    },

    # --- Fan:SystemModel: how design power is derived ---
    ('Fan:SystemModel', 'Design_Power_Sizing_Method'): {
        'PowerPerFlow': 'Electric_Power_Per_Unit_Flow_Rate',
        'PowerPerFlowPerPressure': 'Electric_Power_Per_Unit_Flow_Rate_Per_Unit_Pressure',
        'TotalEfficiencyAndPressure': 'Fan_Total_Efficiency',
    },
    ('Fan:SystemModel', 'Speed_Control_Method'): {
        'Continuous': 'Electric_Power_Function_of_Flow_Fraction_Curve_Name',
        'Discrete': 'Speed_1_Flow_Fraction',  # plus Speed_<n>_Flow_Fraction / _Electric_Power_Fraction pairs
    },
    ('Fan:VariableVolume', 'Fan_Power_Minimum_Flow_Rate_Input_Method'): {
        'Fraction': 'Fan_Power_Minimum_Flow_Fraction',
        'FixedFlowRate': 'Fan_Power_Minimum_Air_Flow_Rate',
    },

    # --- Coil:Heating:Water: capacity input approach ---
    ('Coil:Heating:Water', 'Performance_Input_Method'): {
        'UFactorTimesAreaAndDesignWaterFlowRate': 'U_Factor_Times_Area_Value',
        'NominalCapacity': 'Rated_Capacity',
    },

    # --- Radiative/Convective Units: Heating/Cooling Design Capacity Method pattern ---
    # On the objects that still carry it directly:
    ('ZoneHVAC:Baseboard:RadiantConvective:Electric', 'Heating_Design_Capacity_Method'): {
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
    # On the companion "...:Design" objects (referenced via the parent's "Design Object" field):
    ('ZoneHVAC:Baseboard:RadiantConvective:Water:Design', 'Heating_Design_Capacity_Method'): {
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity',
    },
    ('ZoneHVAC:Baseboard:RadiantConvective:Steam:Design', 'Heating_Design_Capacity_Method'): {
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

    # --- Refrigeration:Case: curve-type selector fields ---
    ('Refrigeration:Case', 'Latent_Case_Credit_Curve_Type'): {
        'CaseTemperatureMethod': 'Latent_Case_Credit_Curve_Name',
        'RelativeHumidityMethod': 'Latent_Case_Credit_Curve_Name',
        'DewpointMethod': 'Latent_Case_Credit_Curve_Name',
    },
    ('Refrigeration:Case', 'Defrost_Energy_Correction_Curve_Type'): {
        'None': None,
        'CaseTemperatureMethod': 'Defrost_Energy_Correction_Curve_Name',
        'RelativeHumidityMethod': 'Defrost_Energy_Correction_Curve_Name',
        'DewpointMethod': 'Defrost_Energy_Correction_Curve_Name',
    },
}

AUTOSIZABLE = {
    ('ZoneHVAC:Baseboard:RadiantConvective:Water', 'Heating_Design_Capacity'),
    ('ZoneHVAC:Baseboard:RadiantConvective:Water', 'Maximum_Water_Flow_Rate'),
    ('ZoneHVAC:Baseboard:RadiantConvective:Steam', 'Heating_Design_Capacity'),
    ('ZoneHVAC:Baseboard:RadiantConvective:Steam', 'Maximum_Steam_Flow_Rate'),
    ('ZoneHVAC:Baseboard:RadiantConvective:Electric', 'Heating_Design_Capacity'),
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Cooling_Design_Capacity'),
    ('ZoneHVAC:CoolingPanel:RadiantConvective:Water', 'Maximum_Chilled_Water_Flow_Rate'),
    ('ZoneHVAC:Baseboard:Convective:Water', 'Heating_Design_Capacity'),
    ('ZoneHVAC:Baseboard:Convective:Water', 'U_Factor_Times_Area_Value'),
    ('ZoneHVAC:Baseboard:Convective:Water', 'Maximum_Water_Flow_Rate'),
    ('ZoneHVAC:Baseboard:Convective:Electric', 'Heating_Design_Capacity'),
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow', 'Hydronic_Tubing_Length'),
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow', 'Heating_Design_Capacity'),
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow', 'Maximum_Hot_Water_Flow'),
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow', 'Cooling_Design_Capacity'),
    ('ZoneHVAC:LowTemperatureRadiant:VariableFlow', 'Maximum_Cold_Water_Flow'),
    ('ZoneHVAC:LowTemperatureRadiant:ConstantFlow', 'Hydronic_Tubing_Length'),
    ('ZoneHVAC:LowTemperatureRadiant:ConstantFlow', 'Rated_Flow_Rate'),
    ('ZoneHVAC:LowTemperatureRadiant:Electric', 'Heating_Design_Capacity'),
    ('ZoneHVAC:HighTemperatureRadiant', 'Heating_Design_Capacity'),
    ('ZoneHVAC:VentilatedSlab', 'Maximum_Air_Flow_Rate'),
    ('ZoneHVAC:VentilatedSlab', 'Minimum_Outdoor_Air_Flow_Rate'),
    ('ZoneHVAC:VentilatedSlab', 'Maximum_Outdoor_Air_Flow_Rate'),
    ('Fan:SystemModel', 'Design_Maximum_Air_Flow_Rate'),
    ('Fan:SystemModel', 'Design_Electric_Power_Consumption'),
    ('Fan:ConstantVolume', 'Maximum_Flow_Rate'),
    ('Fan:VariableVolume', 'Maximum_Flow_Rate'),
    ('Fan:OnOff', 'Maximum_Flow_Rate'),
    ('Fan:ComponentModel', 'Maximum_Flow_Rate'),
    ('Fan:ComponentModel', 'Minimum_Flow_Rate'),
    ('Fan:ComponentModel', 'Motor_Fan_Pulley_Ratio'),
    ('Fan:ComponentModel', 'Belt_Maximum_Torque'),
    ('Fan:ComponentModel', 'Maximum_Motor_Output_Power'),
    ('Fan:ComponentModel', 'Maximum_VFD_Output_Power'),
    ('Coil:Cooling:Water', 'Design_Water_Flow_Rate'),
    ('Coil:Cooling:Water', 'Design_Air_Flow_Rate'),
    ('Coil:Cooling:Water', 'Design_Inlet_Water_Temperature'),
    ('Coil:Cooling:Water', 'Design_Inlet_Air_Temperature'),
    ('Coil:Cooling:Water', 'Design_Outlet_Air_Temperature'),
    ('Coil:Cooling:Water', 'Design_Inlet_Air_Humidity_Ratio'),
    ('Coil:Cooling:Water', 'Design_Outlet_Air_Humidity_Ratio'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Maximum_Water_Flow_Rate'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Tube_Outside_Surface_Area'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Total_Tube_Inside_Area'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Fin_Surface_Area'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Minimum_Airflow_Area'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Coil_Depth'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Fin_Diameter'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Number_of_Tubes_per_Row'),
    ('Coil:Cooling:Water:DetailedGeometry', 'Design_Inlet_Water_Temperature'),
    ('Coil:Cooling:DX:CurveFit:OperatingMode', 'Rated_Gross_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:CurveFit:OperatingMode', 'Rated_Evaporator_Air_Flow_Rate'),
    ('Coil:Cooling:DX:CurveFit:OperatingMode', 'Rated_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:CurveFit:OperatingMode', 'Nominal_Evaporative_Condenser_Pump_Power'),
    ('Coil:Cooling:DX:CurveFit:Speed', 'Gross_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:SingleSpeed', 'Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed', 'Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:SingleSpeed', 'Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:SingleSpeed', 'Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:SingleSpeed', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('Coil:Cooling:DX:TwoSpeed', 'High_Speed_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:TwoSpeed', 'High_Speed_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:TwoSpeed', 'High_Speed_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:TwoSpeed', 'Low_Speed_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:TwoSpeed', 'Low_Speed_Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:TwoSpeed', 'Low_Speed_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:TwoSpeed', 'High_Speed_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:TwoSpeed', 'High_Speed_Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('Coil:Cooling:DX:TwoSpeed', 'Low_Speed_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:TwoSpeed', 'Low_Speed_Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_1_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_1_Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_1_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_1_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_1_Rated_Evaporative_Condenser_Pump_Power_Consumption'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_2_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_2_Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_2_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_2_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_2_Rated_Evaporative_Condenser_Pump_Power_Consumption'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_3_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_3_Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_3_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_3_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_3_Rated_Evaporative_Condenser_Pump_Power_Consumption'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_4_Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_4_Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_4_Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_4_Evaporative_Condenser_Air_Flow_Rate'),
    ('Coil:Cooling:DX:MultiSpeed', 'Speed_4_Rated_Evaporative_Condenser_Pump_Power_Consumption'),
    ('Coil:Cooling:DX:VariableSpeed', 'Gross_Rated_Total_Cooling_Capacity_At_Selected_Nominal_Speed_Level'),
    ('Coil:Cooling:DX:VariableSpeed', 'Rated_Air_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:Cooling:DX:VariableSpeed', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('CoilPerformance:DX:Cooling', 'Gross_Rated_Total_Cooling_Capacity'),
    ('CoilPerformance:DX:Cooling', 'Gross_Rated_Sensible_Heat_Ratio'),
    ('CoilPerformance:DX:Cooling', 'Rated_Air_Flow_Rate'),
    ('CoilPerformance:DX:Cooling', 'Evaporative_Condenser_Air_Flow_Rate'),
    ('CoilPerformance:DX:Cooling', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('Coil:Cooling:DX:VariableRefrigerantFlow', 'Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:VariableRefrigerantFlow', 'Gross_Rated_Sensible_Heat_Ratio'),
    ('Coil:Cooling:DX:VariableRefrigerantFlow', 'Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:VariableRefrigerantFlow', 'Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:VariableRefrigerantFlow', 'Rated_Air_Flow_Rate'),
    ('Coil:Cooling:DX:VariableRefrigerantFlow:FluidTemperatureControl', 'Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:DX:VariableRefrigerantFlow:FluidTemperatureControl', 'Rated_Sensible_Heat_Ratio'),
    ('Coil:Heating:DX:VariableRefrigerantFlow:FluidTemperatureControl', 'Rated_Total_Heating_Capacity'),
    ('Coil:Heating:Water', 'U_Factor_Times_Area_Value'),
    ('Coil:Heating:Water', 'Maximum_Water_Flow_Rate'),
    ('Coil:Heating:Water', 'Rated_Capacity'),
    ('Coil:Heating:Steam', 'Maximum_Steam_Flow_Rate'),
    ('Coil:Heating:Electric', 'Nominal_Capacity'),
    ('Coil:Heating:Electric:MultiStage', 'Stage_1_Nominal_Capacity'),
    ('Coil:Heating:Electric:MultiStage', 'Stage_2_Nominal_Capacity'),
    ('Coil:Heating:Electric:MultiStage', 'Stage_3_Nominal_Capacity'),
    ('Coil:Heating:Electric:MultiStage', 'Stage_4_Nominal_Capacity'),
    ('Coil:Heating:Fuel', 'Nominal_Capacity'),
    ('Coil:Heating:Gas:MultiStage', 'Stage_1_Nominal_Capacity'),
    ('Coil:Heating:Gas:MultiStage', 'Stage_2_Nominal_Capacity'),
    ('Coil:Heating:Gas:MultiStage', 'Stage_3_Nominal_Capacity'),
    ('Coil:Heating:Gas:MultiStage', 'Stage_4_Nominal_Capacity'),
    ('Coil:Heating:DX:SingleSpeed', 'Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:SingleSpeed', 'Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:SingleSpeed', 'Resistive_Defrost_Heater_Capacity'),
    ('Coil:Heating:DX:SingleSpeed', 'Secondary_Coil_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Resistive_Defrost_Heater_Capacity'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_1_Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_1_Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_2_Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_2_Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_3_Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_3_Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_4_Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_4_Rated_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_1_Secondary_Coil_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_2_Secondary_Coil_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_3_Secondary_Coil_Air_Flow_Rate'),
    ('Coil:Heating:DX:MultiSpeed', 'Speed_4_Secondary_Coil_Air_Flow_Rate'),
    ('Coil:Heating:DX:VariableSpeed', 'Rated_Heating_Capacity_At_Selected_Nominal_Speed_Level'),
    ('Coil:Heating:DX:VariableSpeed', 'Rated_Air_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:Heating:DX:VariableSpeed', 'Resistive_Defrost_Heater_Capacity'),
    ('Coil:Cooling:WaterToAirHeatPump:EquationFit', 'Rated_Air_Flow_Rate'),
    ('Coil:Cooling:WaterToAirHeatPump:EquationFit', 'Rated_Water_Flow_Rate'),
    ('Coil:Cooling:WaterToAirHeatPump:EquationFit', 'Gross_Rated_Total_Cooling_Capacity'),
    ('Coil:Cooling:WaterToAirHeatPump:EquationFit', 'Gross_Rated_Sensible_Cooling_Capacity'),
    ('Coil:Cooling:WaterToAirHeatPump:VariableSpeedEquationFit', 'Gross_Rated_Total_Cooling_Capacity_At_Selected_Nominal_Speed_Level'),
    ('Coil:Cooling:WaterToAirHeatPump:VariableSpeedEquationFit', 'Rated_Air_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:Cooling:WaterToAirHeatPump:VariableSpeedEquationFit', 'Rated_Water_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:Heating:WaterToAirHeatPump:EquationFit', 'Rated_Air_Flow_Rate'),
    ('Coil:Heating:WaterToAirHeatPump:EquationFit', 'Rated_Water_Flow_Rate'),
    ('Coil:Heating:WaterToAirHeatPump:EquationFit', 'Gross_Rated_Heating_Capacity'),
    ('Coil:Heating:WaterToAirHeatPump:VariableSpeedEquationFit', 'Rated_Heating_Capacity_At_Selected_Nominal_Speed_Level'),
    ('Coil:Heating:WaterToAirHeatPump:VariableSpeedEquationFit', 'Rated_Air_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:Heating:WaterToAirHeatPump:VariableSpeedEquationFit', 'Rated_Water_Flow_Rate_At_Selected_Nominal_Speed_Level'),
    ('Coil:WaterHeating:AirToWaterHeatPump:Pumped', 'Rated_Evaporator_Air_Flow_Rate'),
    ('Coil:WaterHeating:AirToWaterHeatPump:Pumped', 'Rated_Condenser_Water_Flow_Rate'),
    ('Coil:WaterHeating:AirToWaterHeatPump:Wrapped', 'Rated_Evaporator_Air_Flow_Rate'),
    ('Coil:WaterHeating:AirToWaterHeatPump:VariableSpeed', 'Rated_Evaporator_Air_Flow_Rate'),
    ('Coil:WaterHeating:AirToWaterHeatPump:VariableSpeed', 'Rated_Condenser_Water_Flow_Rate'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Fluid_Storage_Volume'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Ice_Storage_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Rated_Evaporator_Air_Flow_Rate'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Cooling_Only_Mode_Rated_Total_Evaporator_Cooling_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Cooling_And_Charge_Mode_Rated_Total_Evaporator_Cooling_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Cooling_And_Charge_Mode_Rated_Storage_Charging_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Cooling_And_Discharge_Mode_Rated_Total_Evaporator_Cooling_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Cooling_And_Discharge_Mode_Rated_Storage_Discharging_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Charge_Only_Mode_Rated_Storage_Charging_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Discharge_Only_Mode_Rated_Storage_Discharging_Capacity'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Condenser_Design_Air_Flow_Rate'),
    ('Coil:Cooling:DX:SingleSpeed:ThermalStorage', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('EvaporativeCooler:Direct:CelDekPad', 'Direct_Pad_Area'),
    ('EvaporativeCooler:Direct:CelDekPad', 'Direct_Pad_Depth'),
    ('EvaporativeCooler:Indirect:CelDekPad', 'Direct_Pad_Area'),
    ('EvaporativeCooler:Indirect:CelDekPad', 'Direct_Pad_Depth'),
    ('EvaporativeCooler:Indirect:ResearchSpecial', 'Recirculating_Water_Pump_Design_Power'),
    ('EvaporativeCooler:Indirect:ResearchSpecial', 'Secondary_Air_Design_Flow_Rate'),
    ('EvaporativeCooler:Indirect:ResearchSpecial', 'Secondary_Air_Fan_Design_Power'),
    ('EvaporativeCooler:Indirect:ResearchSpecial', 'Primary_Air_Design_Flow_Rate'),
    ('EvaporativeCooler:Direct:ResearchSpecial', 'Primary_Air_Design_Flow_Rate'),
    ('EvaporativeCooler:Direct:ResearchSpecial', 'Recirculating_Water_Pump_Design_Power'),
    ('Humidifier:Steam:Electric', 'Rated_Capacity'),
    ('Humidifier:Steam:Electric', 'Rated_Power'),
    ('Humidifier:Steam:Gas', 'Rated_Capacity'),
    ('Humidifier:Steam:Gas', 'Rated_Gas_Use_Rate'),
    ('HeatExchanger:AirToAir:FlatPlate', 'Nominal_Supply_Air_Flow_Rate'),
    ('HeatExchanger:AirToAir:FlatPlate', 'Nominal_Secondary_Air_Flow_Rate'),
    ('HeatExchanger:AirToAir:SensibleAndLatent', 'Nominal_Supply_Air_Flow_Rate'),
    ('HeatExchanger:Desiccant:BalancedFlow:PerformanceDataType1', 'Nominal_Air_Flow_Rate'),
    ('HeatExchanger:Desiccant:BalancedFlow:PerformanceDataType1', 'Nominal_Air_Face_Velocity'),
    ('AirLoopHVAC:UnitarySystem', 'Minimum_Supply_Air_Temperature'),
    ('AirLoopHVAC:UnitarySystem', 'Cooling_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitarySystem', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitarySystem', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitarySystem', 'Maximum_Supply_Air_Temperature'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_1_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_1_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_2_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_2_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_3_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_3_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_4_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_4_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_5_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_5_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_6_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_6_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_7_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_7_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_8_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_8_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_9_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_9_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Heating_Speed_10_Supply_Air_Flow_Ratio'),
    ('UnitarySystemPerformance:Multispeed', 'Cooling_Speed_10_Supply_Air_Flow_Ratio'),
    ('AirLoopHVAC:Unitary:Furnace:HeatOnly', 'Maximum_Supply_Air_Temperature'),
    ('AirLoopHVAC:Unitary:Furnace:HeatOnly', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'Maximum_Supply_Air_Temperature'),
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'Cooling_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:Unitary:Furnace:HeatCool', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatOnly', 'Maximum_Supply_Air_Temperature'),
    ('AirLoopHVAC:UnitaryHeatOnly', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool', 'Maximum_Supply_Air_Temperature'),
    ('AirLoopHVAC:UnitaryHeatCool', 'Cooling_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir', 'Cooling_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('AirLoopHVAC:UnitaryHeatPump:WaterToAir', 'Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:WaterToAir', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'Cooling_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'Heating_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'Cooling_Outdoor_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'Heating_Outdoor_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatCool:VAVChangeoverBypass', 'No_Load_Outdoor_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Maximum_Supply_Air_Temperature_from_Supplemental_Heater'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'No_Load_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Heating_Speed_1_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Heating_Speed_2_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Heating_Speed_3_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Heating_Speed_4_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Cooling_Speed_1_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Cooling_Speed_2_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Cooling_Speed_3_Supply_Air_Flow_Rate'),
    ('AirLoopHVAC:UnitaryHeatPump:AirToAir:MultiSpeed', 'Cooling_Speed_4_Supply_Air_Flow_Rate'),
    ('AirConditioner:VariableRefrigerantFlow', 'Gross_Rated_Total_Cooling_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow', 'Gross_Rated_Heating_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow', 'Resistive_Defrost_Heater_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow', 'Water_Condenser_Volume_Flow_Rate'),
    ('AirConditioner:VariableRefrigerantFlow', 'Evaporative_Condenser_Air_Flow_Rate'),
    ('AirConditioner:VariableRefrigerantFlow', 'Evaporative_Condenser_Pump_Rated_Power_Consumption'),
    ('AirConditioner:VariableRefrigerantFlow:FluidTemperatureControl', 'Rated_Evaporative_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow:FluidTemperatureControl', 'Resistive_Defrost_Heater_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow:FluidTemperatureControl:HR', 'Rated_Evaporative_Capacity'),
    ('AirConditioner:VariableRefrigerantFlow:FluidTemperatureControl:HR', 'Resistive_Defrost_Heater_Capacity'),
    ('Refrigeration:CompressorRack', 'Evaporative_Condenser_Air_Flow_Rate'),
    ('Refrigeration:CompressorRack', 'Design_Evaporative_Condenser_Water_Pump_Power'),
    ('Refrigeration:Condenser:EvaporativeCooled', 'Rated_Air_Flow_Rate'),
    ('Refrigeration:Condenser:EvaporativeCooled', 'Rated_Water_Pump_Power'),
}

CONSTRAINTS = {
    'AirLoopHVAC:UnitarySystem': [
        'Control_Type = SingleZoneVAV restricts Cooling_Coil_Object_Type to Coil:Cooling:Water, Coil:Cooling:Water:DetailedGeometry, or Coil:Cooling:DX:SingleSpeed.',
        'Control_Type = SingleZoneVAV restricts Heating_Coil_Object_Type to Coil:Heating:Water, Coil:Heating:Fuel, Coil:Heating:Electric, or Coil:Heating:DX:SingleSpeed.',
        'Control_Type = SingleZoneVAV requires Latent_Load_Control = SensibleOnlyLoadControl and is only active during continuous fan operation (cycling fan reverts to Load control).',
        'Use_DOAS_DX_Cooling_Coil = Yes is not compatible with Control_Type = SingleZoneVAV.',
        'Dehumidification_Control_Type = Multimode is only valid when Cooling_Coil_Object_Type = CoilSystem:Cooling:DX:HeatExchangerAssisted.',
        'If no cooling coil is present, set Cooling_Supply_Air_Flow_Rate and/or No_Load_Supply_Air_Flow_Rate to 0 rather than leaving the *_Method fields at None with a coil configured.',
        'DX_Heating_Coil_Sizing_Ratio only affects sizing when the heating coil is a DX coil paired with a larger DX cooling coil (heat pump sizing).',
    ],
    'UnitarySystemPerformance:Multispeed': [
        'Number_of_Speeds_for_Heating and Number_of_Speeds_for_Cooling must match the number of speeds/stages actually defined in the referenced multispeed heating/cooling coil.',
        'Consecutive Speed_N_Supply_Air_Flow_Ratio entries (heating and cooling separately) must be non-decreasing with speed number.',
    ],
    'AirLoopHVAC:Unitary:Furnace:HeatCool': [
        'Cooling_Coil_Object_Type is restricted to Coil:Cooling:DX:SingleSpeed, CoilSystem:Cooling:DX:HeatExchangerAssisted, or Coil:Cooling:DX:VariableSpeed.',
        'Dehumidification_Control_Type = Multimode is only valid when Cooling_Coil_Object_Type = CoilSystem:Cooling:DX:HeatExchangerAssisted.',
    ],
    'AirConditioner:VariableRefrigerantFlow': [
        'All terminal units served by this VRF condensing unit must be listed in the matching ZoneTerminalUnitList object referenced by Zone_Terminal_Unit_List_Name.',
        'Minimum/Maximum_Condenser_Inlet_Node_Temperature_in_Heat_Recovery_Mode are only meaningful when Heat_Pump_Waste_Heat_Recovery = Yes, and must fall outside the cooling-mode and heating-mode condenser temperature limits.',
        'Condenser_Outlet_Node_Name and Water_Condenser_Volume_Flow_Rate are left blank unless Condenser_Type = WaterCooled.',
    ],
    'Coil:Heating:Desuperheater': [
        'Heat reclaim recovery efficiency is capped at 0.3 for most heat-reclaim sources but up to 0.9 when the source is a refrigeration condenser.',
        'Has no autosizable/autocalculatable fields in the IDD: its capacity is fixed by the efficiency and the waste heat available from the source DX coil or refrigeration system, not by sizing.',
    ],
    'CoilSystem:Cooling:Water:HeatExchangerAssisted': [
        'Requires a companion HeatExchanger:AirToAir:FlatPlate/SensibleAndLatent object and a companion Coil:Cooling:Water or Coil:Cooling:Water:DetailedGeometry cooling coil; the wrapper object itself carries no capacity or flow-rate fields of its own (not autosizable).',
    ],
    'CoilSystem:Cooling:DX:HeatExchangerAssisted': [
        'Requires a companion heat exchanger object and companion Coil:Cooling:DX:* coil; the wrapper object itself carries no capacity or flow-rate fields of its own (not autosizable).',
    ],
    'Fan:SystemModel': [
        'Electric_Power_Function_of_Flow_Fraction_Curve_Name is required when Speed_Control_Method = Continuous, or when Number_of_Speeds > 1 and the per-speed power-fraction fields are not used.',
        "Discrete speed control expects Speed_N_Flow_Fraction values arranged in increasing order across the Number_of_Speeds field sets.",
    ],
    'Fan:ZoneExhaust': [
        'Maximum_Flow_Rate has no autosizable/autocalculatable option in the IDD; it must be hard-sized.',
        'Balanced_Exhaust_Fraction_Schedule_Name is ignored (with a warning) if zone air mass flow balance enforcement is active.',
    ],
    'Humidifier:Steam:Gas': [
        'If Rated_Gas_Use_Rate is hard-sized and Inlet_Water_Temperature_Option = FixedInletWaterTemperature, the user-entered Thermal_Efficiency is not used.',
        'If Inlet_Water_Temperature_Option = VariableInletWaterTemperature, Thermal_Efficiency is computed internally and overrides any user entry.',
    ],
    'Dehumidifier:Desiccant:NoFans': [
        'Has no autosizable field in the IDD; Nominal_Process_Air_Flow_Rate must be hard-sized (an initial web summary incorrectly listed it as autosizable).',
        'Default performance-model operation is only valid for process-inlet dry-bulb 1.67-48.9 C and humidity ratio 0.002857-0.02857 kgWater/kgDryAir.',
    ],
    'HeatExchanger:AirToAir:SensibleAndLatent': [
        'Actual supply/exhaust air flow should stay within 50%-130% of Nominal_Supply_Air_Flow_Rate or a simulation warning is issued.',
        'Frost control (when active) takes precedence over Supply_Air_Outlet_Temperature_Control.',
        'The IDD has only one Nominal_Supply_Air_Flow_Rate field (balanced supply/exhaust design), unlike HeatExchanger:AirToAir:FlatPlate which has separate Nominal_Supply_Air_Flow_Rate and Nominal_Secondary_Air_Flow_Rate.',
    ],
    'Refrigeration:Case': [
        'Under_Case_HVAC_Return_Air_Fraction values for all cases returning to the same zone must not sum to more than 1.0.',
        'Case_Height is only meaningful for Anti_Sweat_Heater_Control_Type = HeatBalanceMethod; Humidity_at_Zero_Anti_Sweat_Heater_Energy only for Linear.',
        'Has no autosizable/autocalculatable field in the IDD; all capacity and power-per-length fields must be hard-sized from manufacturer data.',
    ],
    'Refrigeration:CompressorRack': [
        'When Heat_Rejection_Location = Zone and the rack serves walk-ins, all cases on the rack must be in the same zone as the walk-ins.',
        'Heat-reclaim coils require Heat_Rejection_Location = Outdoors; with Zone rejection, reclaim heat is unavailable.',
        'Evaporative_Condenser_Air_Flow_Rate and Design_Evaporative_Condenser_Water_Pump_Power are \\autocalculatable (default Autocalculate), not \\autosizable in the strict IDD sense, and only apply when Condenser_Type = EvaporativelyCooled.',
    ],
}

SECTIONS_READ = [
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-unitary-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-variable-refrigerant-flow-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-radiative-convective-units.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-heating-and-cooling-coils.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-fans.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-humidifiers-and-dehumidifiers.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-evaporative-coolers.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-heat-recovery.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-refrigeration.html',
    'C:/EnergyPlusV9-6-0/Energy+.idd (authoritative source for all field names, \\autosizable / \\autocalculatable markers, and \\key choices; the AUTOSIZABLE set was built by scanning the IDD directly for those two markers, not transcribed from the HTML prose)',
]

IDD_DISAGREEMENTS = [
    "AirLoopHVAC:UnitarySystem: the IDD fields are 'Cooling Fraction of Autosized Cooling Supply Air Flow Rate' and 'Heating Fraction of Autosized Heating Supply Air Flow Rate' (no 'Design' in the name); an initial web summary inserted an extra word ('...Autosized Design Cooling...').",
    "Coil:Heating:Water: the IDD field activated by Performance_Input_Method = NominalCapacity is 'Rated Capacity', not 'Gross Rated Heating Capacity' as an initial web summary called it.",
    "AirConditioner:VariableRefrigerantFlow: the IDD Defrost_Strategy keys are 'ReverseCycle' and 'Resistive' (CamelCase, no hyphen); an initial web summary rendered the first as 'reverse-cycle'.",
    "ZoneHVAC:Baseboard:RadiantConvective:Water, :Steam, ZoneHVAC:LowTemperatureRadiant:VariableFlow and :ConstantFlow: in this IDD these parent objects carry only a 'Design Object' pointer field -- the Heating/Cooling Design Capacity Method fields and their sibling per-floor-area/fraction fields live on separate companion '...:Design' objects (e.g. ZoneHVAC:Baseboard:RadiantConvective:Water:Design). An initial web summary attached the Method fields directly to the parent objects, which is incorrect for this IDD version. ZoneHVAC:VentilatedSlab has no such companion ':Design' object at all in this IDD and has no capacity-method field -- only direct autosizable/autocalculatable flow-rate fields.",
    "Dehumidifier:Desiccant:NoFans: 'Nominal Process Air Flow Rate' has no \\autosizable or \\autocalculatable marker in the IDD; an initial web summary listed it as autosizable.",
    "EvaporativeCooler:Indirect:WetCoil, ZoneHVAC:Dehumidifier:DX, CoilSystem:Cooling:Water(:HeatExchangerAssisted), CoilSystem:Heating:DX, CoilSystem:Cooling:DX(:HeatExchangerAssisted), Coil:Heating:Desuperheater, Coil:Cooling:DX:TwoStageWithHumidityControlMode: none of these objects have any \\autosizable/\\autocalculatable field in the IDD -- confirmed by direct inspection, listed here because their absence from AUTOSIZABLE is a deliberate finding, not an omission.",
    "Refrigeration:CompressorRack: 'Evaporative Condenser Air Flow Rate' and 'Design Evaporative Condenser Water Pump Power' are marked \\autocalculatable (default Autocalculate) in the IDD, not \\autosizable; Refrigeration:Case and all other Refrigeration:* objects except CompressorRack and Condenser:EvaporativeCooled have no autosizable/autocalculatable fields at all.",
]
