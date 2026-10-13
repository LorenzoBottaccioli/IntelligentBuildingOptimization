"""Rules from: Group - Plant-Condenser Loops, Group - Plant-Condenser Control,
Group - Plant Equipment, Group - Water Heaters and Thermal Storage,
Group - Condenser Equipment, Group Solar Collectors, Group Pumps,
Plant-Condenser Flow Control, Group Water Systems.
EnergyPlus 9.6 Input Output Reference (https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/)
Field names, keys, defaults and autosizable markers verified directly against
C:/EnergyPlusV9-6-0/Energy+.idd (parsed programmatically); prose disagreements
are listed in IDD_DISAGREEMENTS below.
"""

GATED = {
    # --- PlantLoop / CondenserLoop ---
    ('PlantLoop', 'User_Defined_Fluid_Type'): {
        'by': 'Fluid_Type', 'when': ('UserDefinedFluidType',),
        'note': 'Only required when Fluid Type = UserDefinedFluidType.'},
    ('CondenserLoop', 'User_Defined_Fluid_Type'): {
        'by': 'Fluid_Type', 'when': ('UserDefinedFluidType',),
        'note': 'Only required when Fluid Type = UserDefinedFluidType.'},
    ('PlantLoop', 'Loop_Circulation_Time'): {
        'by': 'Plant_Loop_Volume', 'when': ('Autocalculate',),
        'note': 'Only used to autocalculate Plant Loop Volume = Loop Circulation Time * Maximum Loop Flow Rate; has no effect if Plant Loop Volume is a hard value.'},
    ('CondenserLoop', 'Loop_Circulation_Time'): {
        'by': 'Condenser_Loop_Volume', 'when': ('Autocalculate',),
        'note': 'Only used to autocalculate Condenser Loop Volume; no effect if Condenser Loop Volume is a hard value.'},

    # --- Plant-Condenser Control ---
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_1_Flow_Rate'): {
        'by': 'Component_1_Object_Type', 'when': ('<specified>',),
        'note': 'Flow rate applies to whichever equipment object is named in the paired Equipment 1 Object Type/Name fields; pattern repeats for slots 1-10.'},
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Non_Charging_Chilled_Water_Temperature'): {
        'by': 'On_Peak_Schedule', 'when': ('<schedule value <= 0>',),
        'note': 'Chiller outlet setpoint used whenever On-Peak Schedule indicates off-peak/non-charging (value <= 0) or it is not cooling season.'},
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Charging_Chilled_Water_Temperature'): {
        'by': 'Charging_Availability_Schedule', 'when': ('<schedule value >= 1>',),
        'note': 'Chiller outlet setpoint used only when Charging Availability Schedule allows charging (value >= 1) during off-peak.'},

    # --- Boilers ---
    ('Boiler:HotWater', 'Design_Water_Flow_Rate'): {
        'by': 'Boiler_Flow_Mode', 'when': ('NotModulated', 'ConstantFlow', 'LeavingSetpointModulated'),
        'note': 'Used by all flow modes but its role differs: full request under ConstantFlow/LeavingSetpointModulated, passive limit under NotModulated.'},

    # --- Chillers: Condenser Type gating (Chiller:Electric, Chiller:ConstantCOP, Chiller:Electric:EIR, Chiller:EngineDriven, Chiller:CombustionTurbine) ---
    ('Chiller:Electric', 'Design_Condenser_Fluid_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': "IDD note actually reads: only used for Condenser Type = AirCooled or EvaporativelyCooled when heat recovery is specified; for WaterCooled the field is the normal condenser design flow. Kept here as the primary WaterCooled sizing field."},
    ('Chiller:Electric', 'Design_Heat_Recovery_Water_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'Heat recovery is only available with Condenser Type = WaterCooled; if non-zero, Heat Recovery Inlet/Outlet Node Names must be entered.'},
    ('Chiller:Electric', 'Heat_Recovery_Inlet_Node_Name'): {
        'by': 'Design_Heat_Recovery_Water_Flow_Rate', 'when': ('<non-zero>',),
        'note': 'Required only when Design Heat Recovery Water Flow Rate is non-zero.'},
    ('Chiller:Electric', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',),
        'note': 'Basin heater fields only apply for Condenser Type = EvaporativelyCooled; heater only runs when the chiller is off and outdoor temp is below the basin heater setpoint.'},
    ('Chiller:Electric', 'Basin_Heater_Setpoint_Temperature'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:Electric', 'Basin_Heater_Operating_Schedule_Name'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:Electric:EIR', 'Condenser_Fan_Power_Ratio'): {
        'by': 'Condenser_Type', 'when': ('AirCooled', 'EvaporativelyCooled'),
        'note': 'Use for air-cooled or evaporatively-cooled condensers only.'},
    ('Chiller:Electric:EIR', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:Electric:EIR', 'Design_Heat_Recovery_Water_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'Heat recovery is only available with Condenser Type = WaterCooled.'},
    ('Chiller:ConstantCOP', 'Design_Condenser_Water_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'Not used for Condenser Type = AirCooled or EvaporativelyCooled.'},
    ('Chiller:ConstantCOP', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:EngineDriven', 'Design_Condenser_Water_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'Not used for Condenser Type = AirCooled or EvaporativelyCooled.'},
    ('Chiller:EngineDriven', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:CombustionTurbine', 'Design_Condenser_Water_Flow_Rate'): {
        'by': 'Condenser_Type', 'when': ('WaterCooled',),
        'note': 'Not used for Condenser Type = AirCooled or EvaporativelyCooled.'},
    ('Chiller:CombustionTurbine', 'Basin_Heater_Capacity'): {
        'by': 'Condenser_Type', 'when': ('EvaporativelyCooled',), 'note': 'Only used for Condenser Type = EvaporativelyCooled.'},
    ('Chiller:CombustionTurbine', 'Turbine_Engine_Efficiency'): {
        'by': 'Gas_Turbine_Engine_Capacity', 'when': ('Autosize',),
        'note': 'Only used when Gas Turbine Engine Capacity is set to Autosize.'},

    # --- Absorption chillers ---
    ('Chiller:Absorption', 'Degree_of_Subcooling_in_Steam_Generator'): {
        'by': 'Generator_Heat_Source_Type', 'when': ('Steam',),
        'note': 'Not used when generator inlet/outlet nodes are not specified, or the generator is connected to a hot water loop.'},
    ('Chiller:Absorption:Indirect', 'Capacity_Correction_Function_of_Generator_Temperature_Curve_Name'): {
        'by': 'Generator_Heat_Source_Type', 'when': ('HotWater',),
        'note': 'Used only when generator fluid type is hot water.'},
    ('Chiller:Absorption:Indirect', 'Degree_of_Subcooling_in_Steam_Generator'): {
        'by': 'Generator_Heat_Source_Type', 'when': ('Steam',),
        'note': 'Not used when generator nodes are unspecified or the generator is connected to a hot water loop.'},
    ('Chiller:Absorption:Indirect', 'Degree_of_Subcooling_in_Steam_Condensate_Loop'): {
        'by': 'Generator_Heat_Source_Type', 'when': ('Steam',),
        'note': 'Not used when generator nodes are unspecified or the generator is connected to a hot water loop.'},

    # --- Water heaters ---
    ('WaterHeater:Mixed', 'Heater_Minimum_Capacity'): {
        'by': 'Heater_Control_Type', 'when': ('Modulate',), 'note': 'Only used when Heater Control Type = Modulate.'},
    ('WaterHeater:Mixed', 'Ambient_Temperature_Schedule_Name'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Schedule',)},
    ('WaterHeater:Mixed', 'Ambient_Temperature_Zone_Name'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Zone',)},
    ('WaterHeater:Mixed', 'Ambient_Temperature_Outdoor_Air_Node_Name'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Outdoors',), 'note': 'Required for Ambient Temperature Indicator = Outdoors.'},
    ('WaterHeater:Mixed', 'Off_Cycle_Loss_Fraction_to_Zone'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Zone',)},
    ('WaterHeater:Mixed', 'On_Cycle_Loss_Fraction_to_Zone'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Zone',)},
    ('WaterHeater:Mixed', 'Peak_Use_Flow_Rate'): {
        'by': 'Use_Side_Inlet_Node_Name', 'when': ('<blank>',), 'note': 'Only used if Use Side node connections are left blank (standalone, non-plant-connected use draw).'},
    ('WaterHeater:Mixed', 'Use_Flow_Rate_Fraction_Schedule_Name'): {
        'by': 'Use_Side_Inlet_Node_Name', 'when': ('<blank>',), 'note': 'Only used if Use Side node connections are left blank.'},
    ('WaterHeater:Mixed', 'Cold_Water_Supply_Temperature_Schedule_Name'): {
        'by': 'Use_Side_Inlet_Node_Name', 'when': ('<blank>',),
        'note': 'Only used if Use Side node connections are left blank; otherwise defaults to Site:WaterMainsTemperature.'},
    ('WaterHeater:Mixed', 'Indirect_Alternate_Setpoint_Temperature_Schedule_Name'): {
        'by': 'Source_Side_Flow_Control_Mode', 'when': ('IndirectHeatAlternateSetpoint',)},
    ('WaterHeater:Stratified', 'Tank_Perimeter'): {
        'by': 'Tank_Shape', 'when': ('Other',), 'note': 'Only used if Tank Shape = Other.'},
    ('WaterHeater:Stratified', 'Ambient_Temperature_Schedule_Name'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Schedule',)},
    ('WaterHeater:Stratified', 'Ambient_Temperature_Zone'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Zone',)},
    ('WaterHeater:Stratified', 'Ambient_Temperature_Outdoor_Air_Node_Name'): {
        'by': 'Ambient_Temperature_Indicator', 'when': ('Outdoors',)},
    ('WaterHeater:Stratified', 'Indirect_Alternate_Setpoint_Temperature_Schedule_Name'): {
        'by': 'Source_Side_Flow_Control_Mode', 'when': ('IndirectHeatAlternateSetpoint',)},
    ('WaterHeater:Sizing', 'Time_Storage_Can_Meet_Peak_Draw'): {
        'by': 'Design_Mode', 'when': ('PeakDraw',)},
    ('WaterHeater:Sizing', 'Time_for_Tank_Recovery'): {
        'by': 'Design_Mode', 'when': ('PeakDraw',)},
    ('WaterHeater:Sizing', 'Nominal_Tank_Volume_for_Autosizing_Plant_Connections'): {
        'by': 'Design_Mode', 'when': ('PeakDraw',),
        'note': 'Only used if Design Mode = PeakDraw and the water heater also has autosized flow rates for demand-side plant connections.'},
    ('WaterHeater:Sizing', 'Number_of_Bedrooms'): {'by': 'Design_Mode', 'when': ('ResidentialHUD-FHAMinimum',)},
    ('WaterHeater:Sizing', 'Number_of_Bathrooms'): {'by': 'Design_Mode', 'when': ('ResidentialHUD-FHAMinimum',)},
    ('WaterHeater:Sizing', 'Storage_Capacity_per_Person'): {'by': 'Design_Mode', 'when': ('PerPerson',)},
    ('WaterHeater:Sizing', 'Recovery_Capacity_per_Person'): {'by': 'Design_Mode', 'when': ('PerPerson',)},
    ('WaterHeater:Sizing', 'Storage_Capacity_per_Floor_Area'): {'by': 'Design_Mode', 'when': ('PerFloorArea',)},
    ('WaterHeater:Sizing', 'Recovery_Capacity_per_Floor_Area'): {'by': 'Design_Mode', 'when': ('PerFloorArea',)},
    ('WaterHeater:Sizing', 'Number_of_Units'): {'by': 'Design_Mode', 'when': ('PerUnit',)},
    ('WaterHeater:Sizing', 'Storage_Capacity_per_Unit'): {'by': 'Design_Mode', 'when': ('PerUnit',)},
    ('WaterHeater:Sizing', 'Recovery_Capacity_PerUnit'): {'by': 'Design_Mode', 'when': ('PerUnit',)},
    ('WaterHeater:Sizing', 'Storage_Capacity_per_Collector_Area'): {'by': 'Design_Mode', 'when': ('PerSolarCollectorArea',)},
    ('WaterHeater:Sizing', 'Height_Aspect_Ratio'): {
        'by': 'WaterHeater_Name', 'when': ('<WaterHeater:Stratified>',), 'note': 'Only used if the referenced water heater is a WaterHeater:Stratified.'},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Inlet_Air_Temperature_Schedule_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('Schedule',)},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Inlet_Air_Zone_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('ZoneAirOnly', 'ZoneAndOutdoorAir')},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Outdoor_Air_Node_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('OutdoorAirOnly', 'ZoneAndOutdoorAir')},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Inlet_Air_Mixer_Node_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('ZoneAndOutdoorAir',)},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Compressor_Ambient_Temperature_Schedule_Name'): {
        'by': 'Compressor_Location', 'when': ('Schedule',)},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Control_Sensor_1_Height_In_Stratified_Tank'): {
        'by': 'Tank_Object_Type', 'when': ('WaterHeater:Stratified',)},
    ('WaterHeater:HeatPump:WrappedCondenser', 'Inlet_Air_Zone_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('ZoneAirOnly', 'ZoneAndOutdoorAir')},
    ('WaterHeater:HeatPump:WrappedCondenser', 'Outdoor_Air_Node_Name'): {
        'by': 'Inlet_Air_Configuration', 'when': ('OutdoorAirOnly', 'ZoneAndOutdoorAir')},

    # --- Cooling towers / evaporative fluid coolers / fluid coolers: Performance Input Method ---
    ('CoolingTower:SingleSpeed', 'Design_Water_Flow_Rate'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',),
        'note': 'Must be blank if Performance Input Method = NominalCapacity.'},
    ('CoolingTower:SingleSpeed', 'Design_U_Factor_Times_Area_Value'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',)},
    ('CoolingTower:SingleSpeed', 'Nominal_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',), 'note': 'Must be blank if Performance Input Method = UFactorTimesAreaAndDesignWaterFlowRate.'},
    ('CoolingTower:SingleSpeed', 'Free_Convection_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',)},
    ('CoolingTower:SingleSpeed', 'Evaporation_Loss_Factor'): {
        'by': 'Evaporation_Loss_Mode', 'when': ('LossFactor',)},
    ('CoolingTower:SingleSpeed', 'Blowdown_Concentration_Ratio'): {
        'by': 'Blowdown_Calculation_Mode', 'when': ('ConcentrationRatio',)},
    ('CoolingTower:SingleSpeed', 'Blowdown_Makeup_Water_Usage_Schedule_Name'): {
        'by': 'Blowdown_Calculation_Mode', 'when': ('ScheduledRate',)},
    ('CoolingTower:SingleSpeed', 'Cell_Minimum__Water_Flow_Rate_Fraction'): {
        'by': 'Cell_Control', 'when': ('MinimalCell', 'MaximalCell'), 'note': 'Only meaningful with Number of Cells > 1.'},
    ('CoolingTower:TwoSpeed', 'Design_Water_Flow_Rate'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',)},
    ('CoolingTower:TwoSpeed', 'Low_Speed_Nominal_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',)},
    ('CoolingTower:TwoSpeed', 'Free_Convection_Nominal_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',)},
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Water_Flow_Rate'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate', 'NominalCapacity'),
        'note': 'Can autocalculate under either method; still gated in the sense that UA fields are only meaningful under UFactorTimesAreaAndDesignWaterFlowRate.'},
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Air_Flow_Rate_U_Factor_Times_Area_Value'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',)},
    ('CoolingTower:VariableSpeed:Merkel', 'Nominal_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',)},
    ('EvaporativeFluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_U_factor_Times_Area_Value'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',)},
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Speed_Standard_Design_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('StandardDesignCapacity',)},
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Speed_User_Specified_Design_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('UserSpecifiedDesignCapacity',)},
    ('FluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_U_factor_Times_Area_Value'): {
        'by': 'Performance_Input_Method', 'when': ('UFactorTimesAreaAndDesignWaterFlowRate',)},
    ('FluidCooler:TwoSpeed', 'Low_Speed_Nominal_Capacity'): {
        'by': 'Performance_Input_Method', 'when': ('NominalCapacity',)},

    # --- HeatExchanger:FluidToFluid ---
    ('HeatExchanger:FluidToFluid', 'Heat_Exchanger_Setpoint_Node_Name'): {
        'by': 'Control_Type', 'when': ('HeatingSetpointModulated', 'HeatingSetpointOnOff', 'CoolingSetpointModulated',
                                        'CoolingSetpointOnOff', 'DualDeadbandSetpointModulated', 'DualDeadbandSetpointOnOff',
                                        'CoolingSetpointOnOffWithComponentOverride'),
        'note': 'Needed whenever Control Type is one of the "*Setpoint*" choices.'},
    ('HeatExchanger:FluidToFluid', 'Component_Override_Loop_Supply_Side_Inlet_Node_Name'): {
        'by': 'Control_Type', 'when': ('CoolingSetpointOnOffWithComponentOverride',)},
    ('HeatExchanger:FluidToFluid', 'Component_Override_Loop_Demand_Side_Inlet_Node_Name'): {
        'by': 'Control_Type', 'when': ('CoolingSetpointOnOffWithComponentOverride',)},
    ('HeatExchanger:FluidToFluid', 'Component_Override_Cooling_Control_Temperature_Mode'): {
        'by': 'Control_Type', 'when': ('CoolingSetpointOnOffWithComponentOverride',)},

    # --- Pumps ---
    ('Pump:VariableSpeed', 'Pump_RPM_Schedule_Name'): {
        'by': 'VFD_Control_Type', 'when': ('ManualControl',)},
    ('Pump:VariableSpeed', 'Minimum_Pressure_Schedule'): {
        'by': 'VFD_Control_Type', 'when': ('PressureSetpointControl',)},
    ('Pump:VariableSpeed', 'Maximum_Pressure_Schedule'): {
        'by': 'VFD_Control_Type', 'when': ('PressureSetpointControl',)},
    ('Pump:VariableSpeed', 'Minimum_RPM_Schedule'): {
        'by': 'VFD_Control_Type', 'when': ('PressureSetpointControl',)},
    ('Pump:VariableSpeed', 'Maximum_RPM_Schedule'): {
        'by': 'VFD_Control_Type', 'when': ('PressureSetpointControl',)},
    ('Pump:VariableSpeed', 'Skin_Loss_Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<specified>',), 'note': 'Only meaningful if Zone Name is populated (pump losses added as an internal gain).'},
    ('Pump:VariableSpeed', 'Design_Electric_Power_per_Unit_Flow_Rate'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlow',)},
    ('Pump:VariableSpeed', 'Design_Shaft_Power_per_Unit_Flow_Rate_per_Unit_Head'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlowPerPressure',)},
    ('Pump:ConstantSpeed', 'Skin_Loss_Radiative_Fraction'): {
        'by': 'Zone_Name', 'when': ('<specified>',)},
    ('Pump:ConstantSpeed', 'Design_Electric_Power_per_Unit_Flow_Rate'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlow',)},
    ('Pump:ConstantSpeed', 'Design_Shaft_Power_per_Unit_Flow_Rate_per_Unit_Head'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlowPerPressure',)},
    ('HeaderedPumps:ConstantSpeed', 'Design_Electric_Power_per_Unit_Flow_Rate'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlow',)},
    ('HeaderedPumps:VariableSpeed', 'Design_Electric_Power_per_Unit_Flow_Rate'): {
        'by': 'Design_Power_Sizing_Method', 'when': ('PowerPerFlow',)},

    # --- Solar collectors ---
    ('SolarCollector:IntegralCollectorStorage', 'Boundary_Condition_Model_Name'): {
        'by': 'Bottom_Surface_Boundary_Conditions_Type', 'when': ('OtherSideConditionsModel',)},
    ('SolarCollectorPerformance:IntegralCollectorStorage', 'Refractive_Index_of_Inner_Cover'): {
        'by': 'Number_of_Covers', 'when': ('2',), 'note': 'Prose-only: only meaningful when Number of Covers >= 2 (dual-cover); IDD has no explicit \\note enforcing this.'},
    ('SolarCollector:FlatPlate:PhotovoltaicThermal', 'Water_Inlet_Node_Name'): {
        'by': 'Thermal_Working_Fluid_Type', 'when': ('Water',)},
    ('SolarCollector:FlatPlate:PhotovoltaicThermal', 'Air_Inlet_Node_Name'): {
        'by': 'Thermal_Working_Fluid_Type', 'when': ('Air',)},
    ('SolarCollectorPerformance:PhotovoltaicThermal:Simple', 'Value_for_Thermal_Conversion_Efficiency_if_Fixed'): {
        'by': 'Thermal_Conversion_Efficiency_Input_Mode_Type', 'when': ('Fixed',)},
    ('SolarCollectorPerformance:PhotovoltaicThermal:Simple', 'Thermal_Conversion_Efficiency_Schedule_Name'): {
        'by': 'Thermal_Conversion_Efficiency_Input_Mode_Type', 'when': ('Scheduled',)},
    ('SolarCollector:UnglazedTranspired', 'Inlet_Node_Name'): {
        'by': 'SolarCollector:UnglazedTranspired:Multisystem', 'when': ('<not used>',),
        'note': 'Required only if this collector is NOT referenced by a SolarCollector:UnglazedTranspired:Multisystem object.'},

    # --- Water systems ---
    ('WaterUse:Connections', 'Drain_Water_Heat_Exchanger_U_Factor_Times_Area'): {
        'by': 'Drain_Water_Heat_Exchanger_Type', 'when': ('Ideal', 'CounterFlow', 'CrossFlow'),
        'note': 'Only used if Drain Water Heat Exchanger Type is not None.'},
    ('WaterUse:Storage', 'Float_Valve_On_Capacity'): {
        'by': 'Type_of_Supply_Controlled_by_Float_Valve', 'when': ('Mains', 'GroundwaterWell', 'OtherTank')},
    ('WaterUse:Storage', 'Float_Valve_Off_Capacity'): {
        'by': 'Type_of_Supply_Controlled_by_Float_Valve', 'when': ('Mains', 'GroundwaterWell', 'OtherTank')},
    ('WaterUse:Storage', 'Other_Tank_Name'): {
        'by': 'Type_of_Supply_Controlled_by_Float_Valve', 'when': ('OtherTank',)},
    ('WaterUse:Storage', 'Water_Temperature_Schedule_Name'): {
        'by': 'Water_Thermal_Mode', 'when': ('ScheduledTemperature',),
        'note': 'Water Thermal Mode = ThermalModel is the only alternative key but is not a fully worked-out model in this IDD version; ScheduledTemperature is the practically usable mode.'},
    ('WaterUse:RainCollector', 'Collection_Loss_Factor_Schedule_Name'): {
        'by': 'Loss_Factor_Mode', 'when': ('Scheduled',)},
    ('WaterUse:RainCollector', 'Collection_Loss_Factor'): {
        'by': 'Loss_Factor_Mode', 'when': ('Constant',)},
    ('WaterUse:Well', 'Water_Table_Depth_Schedule_Name'): {
        'by': 'Water_Table_Depth_Mode', 'when': ('Scheduled',)},
    ('WaterUse:Well', 'Water_Table_Depth'): {
        'by': 'Water_Table_Depth_Mode', 'when': ('Constant',)},
}

METHOD_GROUPS = {
    ('PlantLoop', 'Common_Pipe_Simulation'): {
        'None': 'primary-only, no secondary simulation (fatal error if a demand-side pump exists)',
        'CommonPipe': 'primary-secondary, no temperature control at interface (requires demand-side pump)',
        'TwoWayCommonPipe': 'primary-secondary with control of secondary supply/primary return temperature (requires demand-side pump and a setpoint there)',
        'note': 'Default is None. IDD key is DualSetpointDeadband, not "DualSetpoint" as some prose states (see IDD_DISAGREEMENTS).'},
    ('PlantLoop', 'Plant_Loop_Demand_Calculation_Scheme'): {
        'SingleSetpoint': 'one setpoint manager controls the whole loop', 'DualSetpointDeadband': 'high/low deadband setpoints'},
    ('PlantLoop', 'Load_Distribution_Scheme'): {
        'Optimal': 'each piece of equipment run at its optimal part-load ratio',
        'SequentialLoad': 'equipment loaded in list order up to each one\'s maximum PLR',
        'UniformLoad': 'demand split evenly across all available equipment',
        'SequentialUniformPLR': 'sequential list order, but each active unit run at the same PLR',
        'UniformPLR': 'all units run at a uniform PLR; last unit dropped if total load is insufficient'},
    ('PlantLoop', 'Pressure_Simulation_Type'): {
        'PumpPowerCorrection': 'pump power corrected from pressure drop', 'LoopFlowCorrection': 'loop flow corrected from pressure drop', 'None': 'no pressure simulation'},
    ('PlantEquipmentOperationSchemes', 'Control_Scheme_1_Object_Type'): {
        'PlantEquipmentOperation:Uncontrolled': 'listed equipment always runs when the loop runs',
        'PlantEquipmentOperation:CoolingLoad': 'equipment selected by cooling-load range table',
        'PlantEquipmentOperation:HeatingLoad': 'equipment selected by heating-load range table',
        'PlantEquipmentOperation:ComponentSetpoint': 'equipment selected/sequenced to hit per-component setpoint nodes',
        'PlantEquipmentOperation:ThermalEnergyStorage': 'charge/discharge logic for ice or chilled-water storage plus chillers',
        'PlantEquipmentOperation:UserDefined': 'EMS-driven equipment selection',
        'note': 'Same key set applies to Control Scheme 2..8 Object Type on this object (up to 8 concurrent schemes, each with its own Schedule Name).'},
    ('CondenserEquipmentOperationSchemes', 'Control_Scheme_1_Object_Type'): {
        'PlantEquipmentOperation:Uncontrolled': 'always run', 'PlantEquipmentOperation:CoolingLoad': 'cooling-load range table',
        'PlantEquipmentOperation:HeatingLoad': 'heating-load range table',
        'PlantEquipmentOperation:OutdoorDryBulb': 'outdoor dry-bulb range table', 'PlantEquipmentOperation:OutdoorWetBulb': 'outdoor wet-bulb range table',
        'PlantEquipmentOperation:OutdoorDewpoint': 'outdoor dewpoint range table', 'PlantEquipmentOperation:OutdoorRelativeHumidity': 'outdoor RH range table',
        'PlantEquipmentOperation:OutdoorDryBulbDifference': 'dry-bulb delta-T range table', 'PlantEquipmentOperation:OutdoorWetBulbDifference': 'wet-bulb delta-T range table',
        'PlantEquipmentOperation:OutdoorDewpointDifference': 'dewpoint delta-T range table', 'PlantEquipmentOperation:UserDefined': 'EMS-driven'},
    ('PlantEquipmentOperation:ComponentSetpoint', 'Operation_1_Type'): {
        'Heating': 'component only dispatched to meet a heating setpoint', 'Cooling': 'component only dispatched to meet a cooling setpoint',
        'Dual': 'component can be dispatched either way', 'note': 'Same 3 keys apply to Operation 2..10 Type.'},
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_1_Operation_Type'): {
        'Heating': 'heating dispatch', 'Cooling': 'cooling dispatch (typical for chillers on this scheme)',
        'Dual': 'both directions (required for ice-storage components)', 'note': 'Same keys apply to Component 2..10 Operation Type.'},
    ('Boiler:HotWater', 'Boiler_Flow_Mode'): {
        'NotModulated': 'flow set by the external plant system (variable or constant pumping)',
        'ConstantFlow': 'boiler forces full design flow (constant pumping)',
        'LeavingSetpointModulated': 'boiler varies its own flow to hit a leaving-temperature setpoint (variable pumping)'},
    ('Boiler:HotWater', 'Efficiency_Curve_Temperature_Evaluation_Variable'): {
        'EnteringBoiler': 'efficiency curve evaluated at entering water temperature', 'LeavingBoiler': 'efficiency curve evaluated at leaving water temperature'},
    ('Chiller:Electric', 'Condenser_Type'): {
        'AirCooled': 'no condenser loop; optional condenser nodes, auto-creates an outdoor air node if omitted',
        'WaterCooled': 'full CondenserLoop connection required; condenser nodes and design flow mandatory',
        'EvaporativelyCooled': 'no loop required; enables Basin Heater fields'},
    ('Chiller:Electric', 'Chiller_Flow_Mode'): {
        'NotModulated': 'flow set by external plant system', 'ConstantFlow': 'chiller forces full design flow',
        'LeavingSetpointModulated': 'chiller varies flow to hit leaving-temperature setpoint'},
    ('Chiller:Absorption', 'Generator_Heat_Source_Type'): {
        'Steam': 'default; used whether or not generator nodes are connected to a plant loop',
        'HotWater': 'generator connected to a hot-water plant loop'},
    ('Chiller:Absorption:Indirect', 'Generator_Heat_Source_Type'): {
        'Steam': 'default heat source', 'HotWater': 'activates Capacity Correction Function of Generator Temperature Curve Name'},
    ('Chiller:Electric:ReformulatedEIR', 'Electric_Input_to_Cooling_Output_Ratio_Function_of_Part_Load_Ratio_Curve_Type'): {
        'LeavingCondenserWaterTemperature': 'PLR curve is a function of leaving condenser water temp and PLR (Bicubic/Table:Lookup)',
        'Lift': 'PLR curve is a function of normalized lift and PLR (Curve:ChillerPartLoadWithLiftCurves/Table:Lookup)'},
    ('WaterHeater:Mixed', 'Heater_Control_Type'): {
        'Cycle': 'heater cycles fully on/off around the deadband', 'Modulate': 'heater output varies between Heater Minimum Capacity and Heater Maximum Capacity'},
    ('WaterHeater:Mixed', 'Ambient_Temperature_Indicator'): {
        'Schedule': 'ambient temp from Ambient Temperature Schedule Name', 'Zone': 'ambient temp from a zone (adds loss-to-zone fraction fields)',
        'Outdoors': 'ambient temp from outdoor air node/weather'},
    ('WaterHeater:Mixed', 'Source_Side_Flow_Control_Mode'): {
        'StorageTank': 'always requests source flow unless tank is at its Maximum Temperature Limit',
        'IndirectHeatPrimarySetpoint': 'requests flow whenever the primary setpoint/deadband calls for heat',
        'IndirectHeatAlternateSetpoint': 'requests flow whenever the alternate schedule calls for heat'},
    ('WaterHeater:Stratified', 'Tank_Shape'): {
        'VerticalCylinder': 'default upright tank', 'HorizontalCylinder': 'nodes equal mass, unequal height',
        'Other': 'uniform horizontal cross-section; requires Tank Perimeter'},
    ('WaterHeater:Stratified', 'Heater_Priority_Control'): {
        'MasterSlave': 'heater 1 has priority; only one heater on at a time', 'Simultaneous': 'both heaters can cycle independently'},
    ('WaterHeater:Stratified', 'Inlet_Mode'): {
        'Fixed': 'fluid enters at the specified inlet heights', 'Seeking': 'fluid enters at the node closest to its own temperature (maximizes stratification)'},
    ('WaterHeater:Sizing', 'Design_Mode'): {
        'PeakDraw': 'sized from peak flow x draw/recovery time',
        'ResidentialHUD-FHAMinimum': 'HUD-FHA minimum sizing from bedroom/bathroom count',
        'PerPerson': 'scaled from occupancy', 'PerFloorArea': 'scaled from floor area',
        'PerUnit': 'scaled from an arbitrary unit count', 'PerSolarCollectorArea': 'scaled from solar collector area'},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Inlet_Air_Configuration'): {
        'Schedule': 'inlet air T/RH from schedules (no zone/outdoor node needed)',
        'ZoneAirOnly': 'draws air from Inlet Air Zone Name', 'OutdoorAirOnly': 'draws air from Outdoor Air Node Name',
        'ZoneAndOutdoorAir': 'blended zone/outdoor air via mixer/splitter nodes and Inlet Air Mixer Schedule'},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Tank_Object_Type'): {
        'WaterHeater:Mixed': 'mixed tank model', 'WaterHeater:Stratified': 'stratified tank model (enables Control Sensor Height fields)'},
    ('ThermalStorage:Ice:Detailed', 'Discharging_Curve_Variable_Specifications'): {
        'FractionChargedLMTD': 'curve keyed on fraction charged and LMTD', 'FractionDischargedLMTD': 'curve keyed on fraction discharged and LMTD',
        'LMTDMassFlow': 'curve keyed on LMTD and mass flow', 'LMTDFractionCharged': 'curve keyed on LMTD and fraction charged'},
    ('CoolingTower:SingleSpeed', 'Performance_Input_Method'): {
        'UFactorTimesAreaAndDesignWaterFlowRate': 'sizing driven by Design Water Flow Rate + Design/Free-Convection UA',
        'NominalCapacity': 'sizing driven by Nominal Capacity + Free Convection Capacity (water flow auto-derived at 5.382E-8 m3/s per W)'},
    ('CoolingTower:SingleSpeed', 'Evaporation_Loss_Mode'): {
        'LossFactor': 'user-entered percent-per-K Evaporation Loss Factor', 'SaturatedExit': 'calculated from saturated exit air (no extra input)'},
    ('CoolingTower:SingleSpeed', 'Blowdown_Calculation_Mode'): {
        'ConcentrationRatio': 'blowdown scaled from Blowdown Concentration Ratio', 'ScheduledRate': 'blowdown taken from Blowdown Makeup Water Usage Schedule Name'},
    ('CoolingTower:SingleSpeed', 'Capacity_Control'): {
        'FanCycling': 'fan cycles on/off, PLR by linear interpolation', 'FluidBypass': 'fan runs full speed, water bypass fraction varied'},
    ('CoolingTower:SingleSpeed', 'Cell_Control'): {
        'MinimalCell': 'runs the minimum number of cells needed', 'MaximalCell': 'runs the maximum number of cells allowed'},
    ('EvaporativeFluidCooler:SingleSpeed', 'Performance_Input_Method'): {
        'UFactorTimesAreaAndDesignWaterFlowRate': 'UA + design water flow driven sizing',
        'StandardDesignCapacity': 'capacity at standard AHRI conditions', 'UserSpecifiedDesignCapacity': 'capacity at user-specified design conditions'},
    ('FluidCooler:SingleSpeed', 'Performance_Input_Method'): {
        'UFactorTimesAreaAndDesignWaterFlowRate': 'UA + design water flow driven sizing', 'NominalCapacity': 'nominal capacity driven sizing'},
    ('HeatExchanger:FluidToFluid', 'Heat_Exchange_Model_Type'): {
        'CrossFlowBothUnMixed': 'effectiveness-NTU, both streams unmixed', 'CrossFlowBothMixed': 'effectiveness-NTU, both streams mixed',
        'CrossFlowSupplyMixedDemandUnMixed': 'mixed supply/unmixed demand', 'CrossFlowSupplyUnMixedDemandMixed': 'unmixed supply/mixed demand',
        'ParallelFlow': 'parallel-flow effectiveness-NTU', 'CounterFlow': 'counter-flow effectiveness-NTU', 'Ideal': 'perfect heat transfer, no UA needed'},
    ('HeatExchanger:FluidToFluid', 'Control_Type'): {
        'UncontrolledOn': 'always runs when both loops call for flow', 'OperationSchemeModulated': 'plant operation scheme controls, modulated',
        'OperationSchemeOnOff': 'plant operation scheme controls, on/off', 'HeatingSetpointModulated': 'modulated to hit a heating setpoint node',
        'HeatingSetpointOnOff': 'on/off to hit a heating setpoint node', 'CoolingSetpointModulated': 'modulated to hit a cooling setpoint node',
        'CoolingSetpointOnOff': 'on/off to hit a cooling setpoint node', 'DualDeadbandSetpointModulated': 'modulated within a deadband',
        'DualDeadbandSetpointOnOff': 'on/off within a deadband', 'CoolingDifferentialOnOff': 'on/off based on temperature differential',
        'CoolingSetpointOnOffWithComponentOverride': 'on/off, can override/bypass a downstream component (activates Component Override fields)'},
    ('Pump:VariableSpeed', 'VFD_Control_Type'): {
        'ManualControl': 'flow follows Pump RPM Schedule Name', 'PressureSetpointControl': 'flow follows Min/Max Pressure and RPM schedules'},
    ('Pump:VariableSpeed', 'Pump_Control_Type'): {
        'Continuous': 'pump always runs when the loop is on', 'Intermittent': 'pump runs only when there is a flow request'},
    ('Pump:VariableSpeed', 'Design_Power_Sizing_Method'): {
        'PowerPerFlow': 'Design Power Consumption = Design Max Flow Rate * Design Electric Power per Unit Flow Rate',
        'PowerPerFlowPerPressure': 'Design Power Consumption = Design Max Flow Rate * Design Pump Head * Design Shaft Power per Unit Flow Rate per Unit Head / Motor Efficiency'},
    ('WaterHeater:HeatPump:PumpedCondenser', 'Tank_Element_Control_Logic'): {
        'MutuallyExclusive': 'tank element and heat pump never run together', 'Simultaneous': 'tank element and heat pump can run together'},
    ('SolarCollectorPerformance:FlatPlate', 'Test_Correlation_Type'): {
        'Inlet': 'efficiency correlated to inlet fluid temperature', 'Average': 'efficiency correlated to average fluid temperature', 'Outlet': 'efficiency correlated to outlet fluid temperature'},
    ('SolarCollector:FlatPlate:PhotovoltaicThermal', 'Thermal_Working_Fluid_Type'): {
        'Water': 'connects to a plant loop via Water Inlet/Outlet Node Name', 'Air': 'connects to an air system via Air Inlet/Outlet Node Name'},
    ('SolarCollector:UnglazedTranspired', 'Hole_Layout_Pattern_for_Pitch'): {
        'Square': 'square hole pitch interpretation', 'Triangle': 'triangular hole pitch interpretation'},
    ('SolarCollector:UnglazedTranspired', 'Heat_Exchange_Effectiveness_Correlation'): {
        'Kutscher1994': 'default correlation, does not need Collector Thickness', 'VanDeckerHollandsBrunger2001': 'requires Collector Thickness'},
    ('WaterUse:Storage', 'Type_of_Supply_Controlled_by_Float_Valve'): {
        'None': 'no automatic fill', 'Mains': 'topped up from Site Water Mains', 'GroundwaterWell': 'topped up via a WaterUse:Well object',
        'OtherTank': 'topped up from another WaterUse:Storage tank (Other Tank Name)'},
    ('WaterUse:RainCollector', 'Loss_Factor_Mode'): {
        'Constant': 'fixed Collection Loss Factor', 'Scheduled': 'Collection Loss Factor Schedule Name drives the loss fraction'},
    ('WaterUse:Well', 'Water_Table_Depth_Mode'): {
        'Constant': 'fixed Water Table Depth', 'Scheduled': 'Water Table Depth Schedule Name drives the depth'},
}

AUTOSIZABLE = {
    # --- Loops ---
    ('PlantLoop', 'Maximum_Loop_Flow_Rate'),
    ('PlantLoop', 'Plant_Loop_Volume'),
    ('CondenserLoop', 'Maximum_Loop_Flow_Rate'),
    ('CondenserLoop', 'Condenser_Loop_Volume'),

    # --- Plant/Condenser control component flow rates ---
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_1_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_2_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_3_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_4_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_5_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_6_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_7_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_8_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_9_Flow_Rate'),
    ('PlantEquipmentOperation:ComponentSetpoint', 'Component_10_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_1_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_2_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_3_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_4_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_5_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_6_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_7_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_8_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_9_Flow_Rate'),
    ('PlantEquipmentOperation:ThermalEnergyStorage', 'Component_10_Flow_Rate'),

    # --- Boilers ---
    ('Boiler:HotWater', 'Nominal_Capacity'),
    ('Boiler:HotWater', 'Design_Water_Flow_Rate'),
    ('Boiler:Steam', 'Nominal_Capacity'),

    # --- Chillers ---
    ('Chiller:Electric', 'Nominal_Capacity'),
    ('Chiller:Electric', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:Electric', 'Design_Condenser_Fluid_Flow_Rate'),
    ('Chiller:Electric', 'Design_Heat_Recovery_Water_Flow_Rate'),
    ('Chiller:Electric:EIR', 'Reference_Capacity'),
    ('Chiller:Electric:EIR', 'Reference_Chilled_Water_Flow_Rate'),
    ('Chiller:Electric:EIR', 'Reference_Condenser_Fluid_Flow_Rate'),
    ('Chiller:Electric:EIR', 'Design_Heat_Recovery_Water_Flow_Rate'),
    ('Chiller:Electric:ReformulatedEIR', 'Reference_Capacity'),
    ('Chiller:Electric:ReformulatedEIR', 'Reference_Chilled_Water_Flow_Rate'),
    ('Chiller:Electric:ReformulatedEIR', 'Reference_Condenser_Water_Flow_Rate'),
    ('Chiller:Electric:ReformulatedEIR', 'Design_Heat_Recovery_Water_Flow_Rate'),
    ('Chiller:ConstantCOP', 'Nominal_Capacity'),
    ('Chiller:ConstantCOP', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:ConstantCOP', 'Design_Condenser_Water_Flow_Rate'),
    ('Chiller:EngineDriven', 'Nominal_Capacity'),
    ('Chiller:EngineDriven', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:EngineDriven', 'Design_Condenser_Water_Flow_Rate'),
    ('Chiller:EngineDriven', 'Design_Heat_Recovery_Water_Flow_Rate'),
    ('Chiller:CombustionTurbine', 'Nominal_Capacity'),
    ('Chiller:CombustionTurbine', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:CombustionTurbine', 'Design_Condenser_Water_Flow_Rate'),
    ('Chiller:CombustionTurbine', 'Gas_Turbine_Engine_Capacity'),
    ('Chiller:CombustionTurbine', 'Design_Heat_Recovery_Water_Flow_Rate'),
    ('Chiller:Absorption', 'Nominal_Capacity'),
    ('Chiller:Absorption', 'Nominal_Pumping_Power'),
    ('Chiller:Absorption', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:Absorption', 'Design_Condenser_Water_Flow_Rate'),
    ('Chiller:Absorption', 'Design_Generator_Fluid_Flow_Rate'),
    ('Chiller:Absorption:Indirect', 'Nominal_Capacity'),
    ('Chiller:Absorption:Indirect', 'Nominal_Pumping_Power'),
    ('Chiller:Absorption:Indirect', 'Design_Chilled_Water_Flow_Rate'),
    ('Chiller:Absorption:Indirect', 'Design_Condenser_Water_Flow_Rate'),
    ('Chiller:Absorption:Indirect', 'Design_Generator_Fluid_Flow_Rate'),

    # --- Heat pumps ---
    ('HeatPump:PlantLoop:EIR:Cooling', 'Load_Side_Reference_Flow_Rate'),
    ('HeatPump:PlantLoop:EIR:Cooling', 'Source_Side_Reference_Flow_Rate'),
    ('HeatPump:PlantLoop:EIR:Cooling', 'Reference_Capacity'),
    ('HeatPump:PlantLoop:EIR:Heating', 'Load_Side_Reference_Flow_Rate'),
    ('HeatPump:PlantLoop:EIR:Heating', 'Source_Side_Reference_Flow_Rate'),
    ('HeatPump:PlantLoop:EIR:Heating', 'Reference_Capacity'),
    ('HeatPump:WaterToWater:EquationFit:Cooling', 'Reference_Load_Side_Flow_Rate'),
    ('HeatPump:WaterToWater:EquationFit:Cooling', 'Reference_Source_Side_Flow_Rate'),
    ('HeatPump:WaterToWater:EquationFit:Cooling', 'Reference_Cooling_Capacity'),
    ('HeatPump:WaterToWater:EquationFit:Cooling', 'Reference_Cooling_Power_Consumption'),
    ('HeatPump:WaterToWater:EquationFit:Heating', 'Reference_Load_Side_Flow_Rate'),
    ('HeatPump:WaterToWater:EquationFit:Heating', 'Reference_Source_Side_Flow_Rate'),
    ('HeatPump:WaterToWater:EquationFit:Heating', 'Reference_Heating_Capacity'),
    ('HeatPump:WaterToWater:EquationFit:Heating', 'Reference_Heating_Power_Consumption'),

    # --- District / temperature source ---
    ('DistrictHeating', 'Nominal_Capacity'),
    ('DistrictCooling', 'Nominal_Capacity'),
    ('PlantComponent:TemperatureSource', 'Design_Volume_Flow_Rate'),

    # --- Water heaters and thermal storage ---
    ('WaterHeater:Mixed', 'Tank_Volume'),
    ('WaterHeater:Mixed', 'Heater_Maximum_Capacity'),
    ('WaterHeater:Mixed', 'Use_Side_Design_Flow_Rate'),
    ('WaterHeater:Mixed', 'Source_Side_Design_Flow_Rate'),
    ('WaterHeater:Stratified', 'Tank_Volume'),
    ('WaterHeater:Stratified', 'Tank_Height'),
    ('WaterHeater:Stratified', 'Heater_1_Capacity'),
    ('WaterHeater:Stratified', 'Use_Side_Outlet_Height'),
    ('WaterHeater:Stratified', 'Source_Side_Inlet_Height'),
    ('WaterHeater:Stratified', 'Use_Side_Design_Flow_Rate'),
    ('WaterHeater:Stratified', 'Source_Side_Design_Flow_Rate'),
    ('WaterHeater:HeatPump:PumpedCondenser', 'Condenser_Water_Flow_Rate'),
    ('WaterHeater:HeatPump:PumpedCondenser', 'Evaporator_Air_Flow_Rate'),
    ('WaterHeater:HeatPump:WrappedCondenser', 'Evaporator_Air_Flow_Rate'),
    ('ThermalStorage:ChilledWater:Mixed', 'Use_Side_Design_Flow_Rate'),
    ('ThermalStorage:ChilledWater:Mixed', 'Source_Side_Design_Flow_Rate'),
    ('ThermalStorage:ChilledWater:Stratified', 'Use_Side_Inlet_Height'),
    ('ThermalStorage:ChilledWater:Stratified', 'Source_Side_Outlet_Height'),
    ('ThermalStorage:ChilledWater:Stratified', 'Use_Side_Design_Flow_Rate'),
    ('ThermalStorage:ChilledWater:Stratified', 'Source_Side_Design_Flow_Rate'),

    # --- Cooling towers ---
    ('CoolingTower:SingleSpeed', 'Design_Water_Flow_Rate'),
    ('CoolingTower:SingleSpeed', 'Design_Air_Flow_Rate'),
    ('CoolingTower:SingleSpeed', 'Design_Fan_Power'),
    ('CoolingTower:SingleSpeed', 'Design_U_Factor_Times_Area_Value'),
    ('CoolingTower:SingleSpeed', 'Free_Convection_Regime_Air_Flow_Rate'),
    ('CoolingTower:SingleSpeed', 'Free_Convection_Regime_U_Factor_Times_Area_Value'),
    ('CoolingTower:SingleSpeed', 'Design_Approach_Temperature'),
    ('CoolingTower:SingleSpeed', 'Design_Range_Temperature'),
    ('CoolingTower:SingleSpeed', 'Free_Convection_Capacity'),
    ('CoolingTower:TwoSpeed', 'Design_Water_Flow_Rate'),
    ('CoolingTower:TwoSpeed', 'High_Fan_Speed_Air_Flow_Rate'),
    ('CoolingTower:TwoSpeed', 'High_Fan_Speed_Fan_Power'),
    ('CoolingTower:TwoSpeed', 'High_Fan_Speed_U_Factor_Times_Area_Value'),
    ('CoolingTower:TwoSpeed', 'Low_Fan_Speed_Air_Flow_Rate'),
    ('CoolingTower:TwoSpeed', 'Low_Fan_Speed_Fan_Power'),
    ('CoolingTower:TwoSpeed', 'Low_Fan_Speed_U_Factor_Times_Area_Value'),
    ('CoolingTower:TwoSpeed', 'Free_Convection_Regime_Air_Flow_Rate'),
    ('CoolingTower:TwoSpeed', 'Free_Convection_Regime_U_Factor_Times_Area_Value'),
    ('CoolingTower:TwoSpeed', 'Low_Speed_Nominal_Capacity'),
    ('CoolingTower:TwoSpeed', 'Free_Convection_Nominal_Capacity'),
    ('CoolingTower:TwoSpeed', 'Design_Approach_Temperature'),
    ('CoolingTower:TwoSpeed', 'Design_Range_Temperature'),
    ('CoolingTower:VariableSpeed', 'Design_Water_Flow_Rate'),
    ('CoolingTower:VariableSpeed', 'Design_Air_Flow_Rate'),
    ('CoolingTower:VariableSpeed', 'Design_Fan_Power'),
    ('CoolingTower:VariableSpeed:Merkel', 'Nominal_Capacity'),
    ('CoolingTower:VariableSpeed:Merkel', 'Free_Convection_Nominal_Capacity'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Water_Flow_Rate'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Air_Flow_Rate'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Fan_Power'),
    ('CoolingTower:VariableSpeed:Merkel', 'Free_Convection_Regime_Air_Flow_Rate'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Air_Flow_Rate_U_Factor_Times_Area_Value'),
    ('CoolingTower:VariableSpeed:Merkel', 'Free_Convection_Regime_U_Factor_Times_Area_Value'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Approach_Temperature'),
    ('CoolingTower:VariableSpeed:Merkel', 'Design_Range_Temperature'),

    # --- Evaporative fluid coolers / fluid coolers ---
    ('EvaporativeFluidCooler:SingleSpeed', 'Design_Air_Flow_Rate'),
    ('EvaporativeFluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_Fan_Power'),
    ('EvaporativeFluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_U_factor_Times_Area_Value'),
    ('EvaporativeFluidCooler:SingleSpeed', 'Design_Water_Flow_Rate'),
    ('EvaporativeFluidCooler:TwoSpeed', 'High_Fan_Speed_Air_Flow_Rate'),
    ('EvaporativeFluidCooler:TwoSpeed', 'High_Fan_Speed_Fan_Power'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Fan_Speed_Air_Flow_Rate'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Fan_Speed_Fan_Power'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Speed_Standard_Design_Capacity'),
    ('EvaporativeFluidCooler:TwoSpeed', 'High_Fan_Speed_U_factor_Times_Area_Value'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Fan_Speed_U_factor_Times_Area_Value'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Design_Water_Flow_Rate'),
    ('EvaporativeFluidCooler:TwoSpeed', 'Low_Speed_User_Specified_Design_Capacity'),
    ('FluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_U_factor_Times_Area_Value'),
    ('FluidCooler:SingleSpeed', 'Design_Water_Flow_Rate'),
    ('FluidCooler:SingleSpeed', 'Design_Air_Flow_Rate'),
    ('FluidCooler:SingleSpeed', 'Design_Air_Flow_Rate_Fan_Power'),
    ('FluidCooler:TwoSpeed', 'High_Fan_Speed_U_factor_Times_Area_Value'),
    ('FluidCooler:TwoSpeed', 'Low_Fan_Speed_U_factor_Times_Area_Value'),
    ('FluidCooler:TwoSpeed', 'Low_Speed_Nominal_Capacity'),
    ('FluidCooler:TwoSpeed', 'Design_Water_Flow_Rate'),
    ('FluidCooler:TwoSpeed', 'High_Fan_Speed_Air_Flow_Rate'),
    ('FluidCooler:TwoSpeed', 'High_Fan_Speed_Fan_Power'),
    ('FluidCooler:TwoSpeed', 'Low_Fan_Speed_Air_Flow_Rate'),
    ('FluidCooler:TwoSpeed', 'Low_Fan_Speed_Fan_Power'),

    # --- Heat exchanger ---
    ('HeatExchanger:FluidToFluid', 'Loop_Demand_Side_Design_Flow_Rate'),
    ('HeatExchanger:FluidToFluid', 'Loop_Supply_Side_Design_Flow_Rate'),
    ('HeatExchanger:FluidToFluid', 'Heat_Exchanger_U_Factor_Times_Area_Value'),

    # --- Pumps ---
    ('Pump:VariableSpeed', 'Design_Maximum_Flow_Rate'),
    ('Pump:VariableSpeed', 'Design_Power_Consumption'),
    ('Pump:VariableSpeed', 'Design_Minimum_Flow_Rate'),
    ('Pump:ConstantSpeed', 'Design_Flow_Rate'),
    ('Pump:ConstantSpeed', 'Design_Power_Consumption'),
    ('Pump:VariableSpeed:Condensate', 'Design_Steam_Volume_Flow_Rate'),
    ('Pump:VariableSpeed:Condensate', 'Design_Power_Consumption'),
    ('HeaderedPumps:ConstantSpeed', 'Total_Design_Flow_Rate'),
    ('HeaderedPumps:ConstantSpeed', 'Design_Power_Consumption'),
    ('HeaderedPumps:VariableSpeed', 'Total_Design_Flow_Rate'),
    ('HeaderedPumps:VariableSpeed', 'Design_Power_Consumption'),

    # --- Solar collectors ---
    ('SolarCollector:FlatPlate:PhotovoltaicThermal', 'Design_Flow_Rate'),
}

CONSTRAINTS = {
    'PlantLoop': [
        'Common Pipe Simulation = None with a pump found on the demand side is a fatal error; CommonPipe/TwoWayCommonPipe with no demand-side pump is also a fatal error.',
        'Pressure Simulation Type is currently limited to a single constant-speed "loop pump" per loop side; it is incompatible with Common Pipe simulation and with "branch pump" configurations.',
        'IDD key for Plant Loop Demand Calculation Scheme is DualSetpointDeadband (not "DualSetpoint").',
    ],
    'CondenserLoop': [
        'Same Pressure Simulation Type restriction as PlantLoop: limited to a single constant-speed loop pump, incompatible with common-pipe or branch-pump setups.',
        'CondenserLoop has no Plant Loop Demand Calculation Scheme field (that field exists only on PlantLoop); its setpoint is single-setpoint-node driven via a SetpointManager on the Condenser Loop Temperature Setpoint Node.',
    ],
    'PlantEquipmentOperation:CoolingLoad': [
        'Load Range Upper Limit of one range should equal the Load Range Lower Limit of the next to avoid a gap; EnergyPlus warns on gaps unless an empty equipment list intentionally fills them.',
    ],
    'PlantEquipmentOperation:HeatingLoad': [
        'Same load-range-continuity rule as PlantEquipmentOperation:CoolingLoad.',
    ],
    'PlantEquipmentOperation:ComponentSetpoint': [
        'Boiler and cooling tower components placed on the same condenser loop under this scheme should be wired in parallel branches, not in series, to avoid simultaneous unwanted heating/cooling.',
    ],
    'PlantEquipmentList': [
        'Equipment order sets dispatch priority for load-based schemes (first-listed unit tries to meet demand first).',
        'An empty equipment list for a given load range forces all equipment off for that range.',
    ],
    'Chiller:Electric': [
        'Heat recovery (Design Heat Recovery Water Flow Rate > 0) is only usable with Condenser Type = WaterCooled.',
        'Basin Heater fields only apply when Condenser Type = EvaporativelyCooled, and the basin heater only runs while the chiller itself is off.',
    ],
    'Chiller:Electric:EIR': [
        'Heat recovery requires Condenser Type = WaterCooled; Condenser Fan Power Ratio only applies to AirCooled/EvaporativelyCooled.',
        'Requires three performance curves: Cooling Capacity Function of Temperature, EIR Function of Temperature, and EIR Function of Part Load Ratio.',
    ],
    'Chiller:Electric:ReformulatedEIR': [
        'This model has no Condenser Type field and no Basin Heater/heat-recovery-availability fields tied to condenser type; it is implicitly water-cooled.',
        'The form of the EIR-Function-of-PLR curve depends on Electric Input to Cooling Output Ratio Function of Part Load Ratio Curve Type (LeavingCondenserWaterTemperature -> Bicubic/Table:Lookup; Lift -> Curve:ChillerPartLoadWithLiftCurves/Table:Lookup).',
    ],
    'Chiller:Absorption': [
        'Generator Inlet/Outlet Node Names are optional; if left blank the generator side is not connected to a plant loop and Generator Heat Source Type is treated as Steam regardless of its entry.',
    ],
    'Chiller:Absorption:Indirect': [
        'Capacity Correction Function of Generator Temperature Curve Name is only meaningful when Generator Heat Source Type = HotWater.',
    ],
    'WaterHeater:Mixed': [
        'Maximum Temperature Limit must be greater than the setpoint temperature schedule value at all times.',
        'Peak Use Flow Rate / Use Flow Rate Fraction Schedule / Cold Water Supply Temperature Schedule only apply when the Use Side is NOT connected to a plant loop (nodes blank); once Use Side nodes are wired to a plant loop these fields are ignored.',
    ],
    'WaterHeater:Stratified': [
        'Only Heater 1 Capacity is autosizable; Heater 2 Capacity must always be entered as a hard value.',
        'Number of Nodes is limited to 1-12.',
        'Maximum Temperature Limit must exceed the setpoint schedule value at all times.',
    ],
    'WaterHeater:Sizing': [
        'The recovery temperature range used internally is fixed at 14.4C to 57.2C (58F to 135F) regardless of Design Mode.',
        'Height Aspect Ratio only has an effect when the referenced water heater is a WaterHeater:Stratified with an autosized Tank Height.',
    ],
    'WaterHeater:HeatPump:PumpedCondenser': [
        'Compressor Setpoint Temperature should always be greater than the tank heater setpoint temperature, and the tank heater setpoint should be below the heat-pump cut-in temperature (compressor setpoint minus deadband).',
        'Compressor Location = Zone requires Inlet Air Configuration to be ZoneAirOnly or ZoneAndOutdoorAir.',
    ],
    'ThermalStorage:ChilledWater:Mixed': [
        'Tank Volume is a plain required real in this IDD version, not autosizable, despite being a sizing-relevant field.',
    ],
    'ThermalStorage:ChilledWater:Stratified': [
        'Tank Volume and Tank Height are plain required reals in this IDD version, not autosizable.',
    ],
    'CoolingTower:SingleSpeed': [
        'Design Water Flow Rate, Design U-Factor Times Area Value and Free Convection Regime U-Factor Times Area Value must be blank when Performance Input Method = NominalCapacity, and vice versa for Nominal Capacity / Free Convection Capacity.',
        'If any Free Convection UA or Capacity is non-zero, Free Convection Regime Air Flow Rate must also be non-zero.',
        'Basin Heater only operates when the tower fan is off and no water is flowing through the tower.',
    ],
    'CoolingTower:TwoSpeed': [
        'Low Fan Speed values must stay between the Free Convection and High Fan Speed values (air flow, UA, capacity all ordered Free Convection < Low < High).',
    ],
    'HeatExchanger:FluidToFluid': [
        'Heat Exchanger Setpoint Node Name is required whenever Control Type contains "Setpoint".',
        'Component Override fields are only used, and only meaningful, when Control Type = CoolingSetpointOnOffWithComponentOverride.',
    ],
    'GroundHeatExchanger': [
        'Design Flow Rate on GroundHeatExchanger:System, GroundHeatExchanger:Slinky and GroundHeatExchanger:HorizontalTrench is a plain required real in the IDD, not autosizable, despite being sizing-relevant (see IDD_DISAGREEMENTS).',
    ],
    'TemperingValve': [
        'Only two paths (main + tempering) are allowed in the splitter/mixer pair associated with a TemperingValve; bypasses are not allowed there.',
        'No other Connector:Splitter/Connector:Mixer pair may be used on the supply side of the same plant loop.',
        'The valve only acts when the Stream 2 Source Node is warmer than the setpoint and the main inlet flow is cooler than the setpoint.',
    ],
    'WaterUse:Storage': [
        'If Maximum Capacity is left blank the tank is treated as having unlimited capacity; if Design In/Out Flow Rate is blank that flow is treated as unlimited.',
        'Water Thermal Mode = ThermalModel is a defined key but has no fully worked sizing/behavior documented beyond ScheduledTemperature; treat ThermalModel-dependent fields (Ambient Temperature Indicator/Schedule/Zone, Tank Surface Area, Tank U Value, Tank Outside Surface Material Name) as not meaningfully optimizable in this version.',
    ],
    'WaterUse:Well': [
        'Several fields (Pump Depth, Pump Rated Head, Pump Efficiency, Well Recovery Rate, Nominal Well Storage Volume) are accepted by the IDD but described in the reference as reserved for future use; changing them has no simulated effect.',
        'Well operation is governed by its associated WaterUse:Storage object, not directly by the well\'s own schedule fields.',
    ],
    'SolarCollector:FlatPlate:Water': [
        'Maximum Flow Rate is a plain optional real in the IDD, not autosizable, despite sizing-oriented prose elsewhere (see IDD_DISAGREEMENTS).',
    ],
    'SolarCollector:IntegralCollectorStorage': [
        'Maximum Flow Rate is a plain optional real in the IDD, not autosizable (see IDD_DISAGREEMENTS).',
        'ICS Collector Type currently only supports RectangularTank.',
    ],
}

SECTIONS_READ = [
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-plant-condenser-loops.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-plant-condenser-control.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-plant-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-water-heaters.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-condenser-equipment.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-solar-collectors.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-pumps.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-plant-condenser-flow-control.html',
    'https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/group-water-systems.html',
]

IDD_DISAGREEMENTS = [
    'PlantLoop "Plant Loop Demand Calculation Scheme" key is DualSetpointDeadband in Energy+.idd; some prose/summaries shorten it to "DualSetpoint".',
    'GroundHeatExchanger:System, GroundHeatExchanger:Slinky and GroundHeatExchanger:HorizontalTrench "Design Flow Rate" is a plain required real (no \\autosizable/\\autocalculatable marker) in Energy+.idd, even though several summaries describe it as autosizable via a Sizing:Plant object.',
    'ThermalStorage:ChilledWater:Mixed "Tank Volume" and ThermalStorage:ChilledWater:Stratified "Tank Volume"/"Tank Height" are plain required reals in Energy+.idd, not autosizable, despite being analogous to the autosizable Tank Volume/Height fields on WaterHeater:Mixed/Stratified.',
    'SolarCollector:FlatPlate:Water and SolarCollector:IntegralCollectorStorage "Maximum Flow Rate" are plain optional reals in Energy+.idd (no autosizable marker), unlike SolarCollector:FlatPlate:PhotovoltaicThermal "Design Flow Rate", which is genuinely \\autosizable.',
    'Chiller:Electric "Design Condenser Fluid Flow Rate" carries an IDD \\note saying it is "only used for Condenser Type = AirCooled or EvaporativelyCooled when Heat Recovery is specified" -- i.e. by the literal note it is NOT the WaterCooled condenser design-flow field, even though it is the only condenser-flow-rate field on the object and prose summaries treat it as the general condenser design flow for all condenser types.',
]
