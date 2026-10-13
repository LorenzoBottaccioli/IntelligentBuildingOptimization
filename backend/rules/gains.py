"""Rules from: group-internal-gains-people-lights-other, group-daylighting,
group-exterior-energy-use-equipment, group-airflow, group-airflow-network,
group-design-objects (EnergyPlus 9.6 Input Output Reference, BigLadder).

Field names use underscores in place of spaces/hyphens/slashes, as eppy spells
them. Every field/key name below was checked against C:/EnergyPlusV9-6-0/Energy+.idd;
where the prose text and the IDD disagreed, the IDD spelling was used (see
IDD_DISAGREEMENTS).
"""

GATED = {
    # ---- People ----
    ('People', 'Surface_Name_Angle_Factor_List_Name'): {
        'by': 'Mean_Radiant_Temperature_Calculation_Type', 'when': ('SurfaceWeighted', 'AngleFactor'),
        'note': 'Only read when MRT calc type is SurfaceWeighted or AngleFactor; ignored for ZoneAveraged.'},
    ('People', 'Clothing_Insulation_Calculation_Method_Schedule_Name'): {
        'by': 'Clothing_Insulation_Calculation_Method', 'when': ('CalculationMethodSchedule',),
        'note': 'Only used when the clothing method is CalculationMethodSchedule (schedule value 1=Scheduled, 2=DynamicClothingModelASHRAE55).'},
    ('People', 'Clothing_Insulation_Schedule_Name'): {
        'by': 'Clothing_Insulation_Calculation_Method', 'when': ('ClothingInsulationSchedule', 'CalculationMethodSchedule'),
        'note': 'Supplies the clo value when the method is ClothingInsulationSchedule (or the Scheduled branch of CalculationMethodSchedule); also requires a thermal comfort model to be selected or it is reported unused.'},
    ('People', 'Work_Efficiency_Schedule_Name'): {
        'by': 'Thermal_Comfort_Model_1_Type', 'when': ('Fanger', 'Pierce', 'KSU', 'CoolingEffectASH55', 'AnkleDraftASH55'),
        'note': 'Only required to run one of the thermal comfort models Fanger, Pierce, KSU, CoolingEffectASH55 or AnkleDraftASH55, selected via any of the Thermal Comfort Model 1-7 Type fields.'},
    ('People', 'Air_Velocity_Schedule_Name'): {
        'by': 'Thermal_Comfort_Model_1_Type', 'when': ('Fanger', 'Pierce', 'KSU', 'CoolingEffectASH55', 'AnkleDraftASH55'),
        'note': 'Only required to run Fanger, Pierce, KSU, CoolingEffectASH55 or AnkleDraftASH55, selected via any Thermal Comfort Model Type field.'},
    ('People', 'Ankle_Level_Air_Velocity_Schedule_Name'): {
        'by': 'Thermal_Comfort_Model_1_Type', 'when': ('AnkleDraftASH55',),
        'note': 'Only required for runs of the AnkleDraftASH55 thermal comfort model, selected via any Thermal Comfort Model Type field.'},
    # ---- Lights ----
    ('Lights', 'Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_1'): {
        'by': 'Return_Air_Fraction_Calculated_from_Plenum_Temperature', 'when': ('Yes',),
        'note': 'Used only if Return Air Fraction Is Calculated from Plenum Temperature = Yes.'},
    ('Lights', 'Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_2'): {
        'by': 'Return_Air_Fraction_Calculated_from_Plenum_Temperature', 'when': ('Yes',),
        'note': 'Used only if Return Air Fraction Is Calculated from Plenum Temperature = Yes.'},
    # ---- ElectricEquipment:ITE:AirCooled ----
    ('ElectricEquipment:ITE:AirCooled', 'Air_Inlet_Connection_Type'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowFromSystem',),
        'note': 'This field is only used when Air Flow Calculation Method is FlowFromSystem.'},
    ('ElectricEquipment:ITE:AirCooled', 'Design_Recirculation_Fraction'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowFromSystem',),
        'note': 'Only used when Air Flow Calculation Method is FlowFromSystem, and only if Air Inlet Connection Type = AdjustedSupply.'},
    ('ElectricEquipment:ITE:AirCooled', 'Recirculation_Function_of_Loading_and_Supply_Temperature_Curve_Name'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowFromSystem',),
        'note': 'Only used when Air Flow Calculation Method is FlowFromSystem, and only if Air Inlet Connection Type = AdjustedSupply.'},
    ('ElectricEquipment:ITE:AirCooled', 'Supply_Temperature_Difference'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowControlWithApproachTemperatures',),
        'note': 'Ignored when Air Flow Calculation Method is FlowFromSystem; required (with or via its schedule) for FlowControlWithApproachTemperatures.'},
    ('ElectricEquipment:ITE:AirCooled', 'Supply_Temperature_Difference_Schedule'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowControlWithApproachTemperatures',),
        'note': 'Ignored when Air Flow Calculation Method is FlowFromSystem.'},
    ('ElectricEquipment:ITE:AirCooled', 'Return_Temperature_Difference'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowControlWithApproachTemperatures',),
        'note': 'Ignored when Air Flow Calculation Method is FlowFromSystem; required (with or via its schedule) for FlowControlWithApproachTemperatures.'},
    ('ElectricEquipment:ITE:AirCooled', 'Return_Temperature_Difference_Schedule'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowControlWithApproachTemperatures',),
        'note': 'Ignored when Air Flow Calculation Method is FlowFromSystem.'},
    ('ElectricEquipment:ITE:AirCooled', 'Supply_Air_Node_Name'): {
        'by': 'Air_Flow_Calculation_Method', 'when': ('FlowControlWithApproachTemperatures',),
        'note': 'Required if Air Flow Calculation Method = FlowControlWithApproachTemperatures (also required if Air Inlet Connection Type = AdjustedSupply, or if Supply Heat Index reporting is desired).'},
    # ---- ZoneVentilation:DesignFlowRate ----
    ('ZoneVentilation:DesignFlowRate', 'Fan_Pressure_Rise'): {
        'by': 'Ventilation_Type', 'when': ('Intake', 'Exhaust', 'Balanced'),
        'note': 'For Natural ventilation, fan pressure and efficiency values are ignored; for Intake/Exhaust/Balanced they define fan electric consumption.'},
    ('ZoneVentilation:DesignFlowRate', 'Fan_Total_Efficiency'): {
        'by': 'Ventilation_Type', 'when': ('Intake', 'Exhaust', 'Balanced'),
        'note': 'For Natural ventilation this value is ignored; for Intake/Exhaust/Balanced it defines fan electric consumption.'},
    # ---- ZoneVentilation:WindandStackOpenArea ----
    ('ZoneVentilation:WindandStackOpenArea', 'Effective_Angle'): {
        'by': 'Opening_Effectiveness', 'when': ('Autocalculate',),
        'note': 'Used only when Opening Effectiveness = Autocalculate, to interpolate Cw between 0.55 (angle=0) and 0.3 (angle=180).'},
    # ---- DesignSpecification:OutdoorAir ----
    ('DesignSpecification:OutdoorAir', 'Outdoor_Air_Flow_per_Person'): {
        'by': 'Outdoor_Air_Method', 'when': ('Flow/Person', 'Sum', 'Maximum'),
        'note': 'Only used if Outdoor Air Method is Flow/Person, Sum, or Maximum.'},
    ('DesignSpecification:OutdoorAir', 'Outdoor_Air_Flow_per_Zone_Floor_Area'): {
        'by': 'Outdoor_Air_Method', 'when': ('Flow/Area', 'Sum', 'Maximum'),
        'note': 'Only used if Outdoor Air Method is Flow/Area, Sum, or Maximum.'},
    ('DesignSpecification:OutdoorAir', 'Outdoor_Air_Flow_per_Zone'): {
        'by': 'Outdoor_Air_Method', 'when': ('Flow/Zone', 'Sum', 'Maximum'),
        'note': 'Only used if Outdoor Air Method is Flow/Zone, Sum, or Maximum.'},
    ('DesignSpecification:OutdoorAir', 'Outdoor_Air_Flow_Air_Changes_per_Hour'): {
        'by': 'Outdoor_Air_Method', 'when': ('AirChanges/Hour', 'Sum', 'Maximum'),
        'note': 'Only used if Outdoor Air Method is AirChanges/Hour, Sum, or Maximum.'},
    ('DesignSpecification:OutdoorAir', 'Proportional_Control_Minimum_Outdoor_Air_Flow_Rate_Schedule_Name'): {
        'by': 'System_Outdoor_Air_Method', 'when': ('ProportionalControlBasedOnDesignOARate',),
        'note': 'Gating field lives on Controller:MechanicalVentilation, not this object; only used to compute the minimum OA flow rate when System Outdoor Air Method = ProportionalControlBasedOnDesignOARate.'},
    # ---- DesignSpecification:ZoneAirDistribution ----
    ('DesignSpecification:ZoneAirDistribution', 'Zone_Air_Distribution_Effectiveness_in_Cooling_Mode'): {
        'by': 'Zone_Air_Distribution_Effectiveness_Schedule_Name', 'when': ('<blank>',),
        'note': 'Ignored whenever the effectiveness schedule is specified; the schedule replaces both the cooling and heating mode constants.'},
    ('DesignSpecification:ZoneAirDistribution', 'Zone_Air_Distribution_Effectiveness_in_Heating_Mode'): {
        'by': 'Zone_Air_Distribution_Effectiveness_Schedule_Name', 'when': ('<blank>',),
        'note': 'Ignored whenever the effectiveness schedule is specified; the schedule replaces both the cooling and heating mode constants.'},
    # ---- Daylighting:Controls ----
    ('Daylighting:Controls', 'Glare_Calculation_Daylighting_Reference_Point_Name'): {
        'by': 'Daylighting_Method', 'when': ('SplitFlux',),
        'note': 'Glare calculation is only performed for the SplitFlux method; ignored when Daylighting Method = DElight.'},
    ('Daylighting:Controls', 'Glare_Calculation_Azimuth_Angle_of_View_Direction_Clockwise_from_Zone_y_Axis'): {
        'by': 'Daylighting_Method', 'when': ('SplitFlux',),
        'note': 'Only used with SplitFlux glare calculation; ignored for DElight.'},
    ('Daylighting:Controls', 'Maximum_Allowable_Discomfort_Glare_Index'): {
        'by': 'Daylighting_Method', 'when': ('SplitFlux',),
        'note': 'Only used with SplitFlux glare calculation; ignored for DElight.'},
    ('Daylighting:Controls', 'DElight_Gridding_Resolution'): {
        'by': 'Daylighting_Method', 'when': ('DElight',),
        'note': 'Only used when Daylighting Method = DElight; ignored for SplitFlux.'},
    ('Daylighting:Controls', 'Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control'): {
        'by': 'Lighting_Control_Type', 'when': ('Continuous', 'ContinuousOff'),
        'note': 'Only applies to Continuous/ContinuousOff dimming; not used for Stepped control.'},
    ('Daylighting:Controls', 'Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control'): {
        'by': 'Lighting_Control_Type', 'when': ('Continuous', 'ContinuousOff'),
        'note': 'Only applies to Continuous/ContinuousOff dimming; not used for Stepped control.'},
    ('Daylighting:Controls', 'Number_of_Stepped_Control_Steps'): {
        'by': 'Lighting_Control_Type', 'when': ('Stepped',),
        'note': 'Required and must be greater than zero only if Lighting Control Type = Stepped.'},
    ('Daylighting:Controls', 'Probability_Lighting_will_be_Reset_When_Needed_in_Manual_Stepped_Control'): {
        'by': 'Lighting_Control_Type', 'when': ('Stepped',),
        'note': 'Only meaningful for manual Stepped control systems.'},
    # ---- AirflowNetwork:SimulationControl ----
    ('AirflowNetwork:SimulationControl', 'Height_Selection_for_Local_Wind_Pressure_Calculation'): {
        'by': 'Wind_Pressure_Coefficient_Type', 'when': ('Input',),
        'note': 'Ignored when Wind Pressure Coefficient Type = SurfaceAverageCalculation.'},
    ('AirflowNetwork:SimulationControl', 'Building_Type'): {
        'by': 'Wind_Pressure_Coefficient_Type', 'when': ('SurfaceAverageCalculation',),
        'note': 'Used only if Wind Pressure Coefficient Type = SurfaceAverageCalculation; otherwise may be left blank.'},
    ('AirflowNetwork:SimulationControl', 'Azimuth_Angle_of_Long_Axis_of_Building'): {
        'by': 'Wind_Pressure_Coefficient_Type', 'when': ('SurfaceAverageCalculation',),
        'note': 'Used only if Wind Pressure Coefficient Type = SurfaceAverageCalculation.'},
    ('AirflowNetwork:SimulationControl', 'Ratio_of_Building_Width_Along_Short_Axis_to_Width_Along_Long_Axis'): {
        'by': 'Wind_Pressure_Coefficient_Type', 'when': ('SurfaceAverageCalculation',),
        'note': 'Used only if Wind Pressure Coefficient Type = SurfaceAverageCalculation.'},
    # ---- AirflowNetwork:MultiZone:Zone ----
    ('AirflowNetwork:MultiZone:Zone', 'Ventilation_Control_Zone_Temperature_Setpoint_Schedule_Name'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Temperature', 'Enthalpy'),
        'note': 'Used only if Ventilation Control Mode = Temperature or Enthalpy.'},
    ('AirflowNetwork:MultiZone:Zone', 'Minimum_Venting_Open_Factor'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Temperature', 'Enthalpy'),
        'note': 'Used only if Ventilation Control Mode = Temperature or Enthalpy.'},
    ('AirflowNetwork:MultiZone:Zone', 'Indoor_and_Outdoor_Temperature_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Temperature',),
        'note': 'Applicable only if Ventilation Control Mode = Temperature.'},
    ('AirflowNetwork:MultiZone:Zone', 'Indoor_and_Outdoor_Temperature_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Temperature',),
        'note': 'Applicable only if Ventilation Control Mode = Temperature.'},
    ('AirflowNetwork:MultiZone:Zone', 'Indoor_and_Outdoor_Enthalpy_Difference_Lower_Limit_For_Maximum_Venting_Open_Factor'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Enthalpy',),
        'note': 'Applicable only if Ventilation Control Mode = Enthalpy.'},
    ('AirflowNetwork:MultiZone:Zone', 'Indoor_and_Outdoor_Enthalpy_Difference_Upper_Limit_for_Minimum_Venting_Open_Factor'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Enthalpy',),
        'note': 'Applicable only if Ventilation Control Mode = Enthalpy.'},
    ('AirflowNetwork:MultiZone:Zone', 'Venting_Availability_Schedule_Name'): {
        'by': 'Ventilation_Control_Mode', 'when': ('Temperature', 'Enthalpy', 'Constant', 'ASHRAE55Adaptive', 'CEN15251Adaptive'),
        'note': 'Not used if Ventilation Control Mode = NoVent (windows/doors are always closed in that mode).'},
    ('AirflowNetwork:MultiZone:Zone', 'Facade_Width'): {
        'by': 'Single_Sided_Wind_Pressure_Coefficient_Algorithm', 'when': ('Advanced',),
        'note': 'Only meaningful when the Advanced single-sided algorithm is selected, and only valid for zones with 2 openings on one facade.'},
    # ---- Sizing:Zone ----
    ('Sizing:Zone', 'Zone_Cooling_Design_Supply_Air_Temperature'): {
        'by': 'Zone_Cooling_Design_Supply_Air_Temperature_Input_Method', 'when': ('SupplyAirTemperature',),
        'note': 'Only used when the input method is SupplyAirTemperature.'},
    ('Sizing:Zone', 'Zone_Cooling_Design_Supply_Air_Temperature_Difference'): {
        'by': 'Zone_Cooling_Design_Supply_Air_Temperature_Input_Method', 'when': ('TemperatureDifference',),
        'note': 'Only used when the input method is TemperatureDifference (subtracted from zone temperature at peak load).'},
    ('Sizing:Zone', 'Zone_Heating_Design_Supply_Air_Temperature'): {
        'by': 'Zone_Heating_Design_Supply_Air_Temperature_Input_Method', 'when': ('SupplyAirTemperature',),
        'note': 'Only used when the input method is SupplyAirTemperature.'},
    ('Sizing:Zone', 'Zone_Heating_Design_Supply_Air_Temperature_Difference'): {
        'by': 'Zone_Heating_Design_Supply_Air_Temperature_Input_Method', 'when': ('TemperatureDifference',),
        'note': 'Only used when the input method is TemperatureDifference (added to zone temperature at peak load).'},
    ('Sizing:Zone', 'Cooling_Design_Air_Flow_Rate'): {
        'by': 'Cooling_Design_Air_Flow_Method', 'when': ('Flow/Zone',),
        'note': 'Only used if Cooling Design Air Flow Method = Flow/Zone.'},
    ('Sizing:Zone', 'Cooling_Minimum_Air_Flow_per_Zone_Floor_Area'): {
        'by': 'Cooling_Design_Air_Flow_Method', 'when': ('DesignDayWithLimit',),
        'note': 'Only used if Cooling Design Air Flow Method = DesignDayWithLimit.'},
    ('Sizing:Zone', 'Cooling_Minimum_Air_Flow'): {
        'by': 'Cooling_Design_Air_Flow_Method', 'when': ('DesignDayWithLimit',),
        'note': 'Only used if Cooling Design Air Flow Method = DesignDayWithLimit.'},
    ('Sizing:Zone', 'Heating_Design_Air_Flow_Rate'): {
        'by': 'Heating_Design_Air_Flow_Method', 'when': ('Flow/Zone',),
        'note': 'Only used if Heating Design Air Flow Method = Flow/Zone.'},
    ('Sizing:Zone', 'Heating_Maximum_Air_Flow_per_Zone_Floor_Area'): {
        'by': 'Heating_Design_Air_Flow_Method', 'when': ('Flow/Zone', 'DesignDayWithLimit'),
        'note': 'Used to size the heating flow rate when method = Flow/Zone, and for autosizing components when method = DesignDayWithLimit.'},
    ('Sizing:Zone', 'Heating_Maximum_Air_Flow'): {
        'by': 'Heating_Design_Air_Flow_Method', 'when': ('DesignDayWithLimit',),
        'note': 'Used for autosizing components when Heating Design Air Flow Method = DesignDayWithLimit.'},
    ('Sizing:Zone', 'Dedicated_Outdoor_Air_System_Control_Strategy'): {
        'by': 'Account_for_Dedicated_Outdoor_Air_System', 'when': ('Yes',),
        'note': 'DOAS control strategy and setpoint fields are only relevant when a DOAS is accounted for.'},
    ('Sizing:Zone', 'Dedicated_Outdoor_Air_Low_Setpoint_Temperature_for_Design'): {
        'by': 'Account_for_Dedicated_Outdoor_Air_System', 'when': ('Yes',),
        'note': 'Only relevant when Account for Dedicated Outdoor Air System = Yes.'},
    ('Sizing:Zone', 'Dedicated_Outdoor_Air_High_Setpoint_Temperature_for_Design'): {
        'by': 'Account_for_Dedicated_Outdoor_Air_System', 'when': ('Yes',),
        'note': 'Only relevant when Account for Dedicated Outdoor Air System = Yes.'},
}

METHOD_GROUPS = {
    ('People', 'Number_of_People_Calculation_Method'): {
        'People': 'Number_of_People',
        'People/Area': 'People_per_Floor_Area',
        'Area/Person': 'Floor_Area_per_Person'},
    ('Lights', 'Design_Level_Calculation_Method'): {
        'LightingLevel': 'Lighting_Level',
        'Watts/Area': 'Watts_per_Zone_Floor_Area',
        'Watts/Person': 'Watts_per_Person'},
    ('ElectricEquipment', 'Design_Level_Calculation_Method'): {
        'EquipmentLevel': 'Design_Level',
        'Watts/Area': 'Watts_per_Zone_Floor_Area',
        'Watts/Person': 'Watts_per_Person'},
    ('GasEquipment', 'Design_Level_Calculation_Method'): {
        'EquipmentLevel': 'Design_Level',
        'Watts/Area': 'Power_per_Zone_Floor_Area',
        'Watts/Person': 'Power_per_Person',
        'Power/Area': 'Power_per_Zone_Floor_Area',
        'Power/Person': 'Power_per_Person'},
    ('HotWaterEquipment', 'Design_Level_Calculation_Method'): {
        'EquipmentLevel': 'Design_Level',
        'Watts/Area': 'Power_per_Zone_Floor_Area',
        'Watts/Person': 'Power_per_Person',
        'Power/Area': 'Power_per_Zone_Floor_Area',
        'Power/Person': 'Power_per_Person'},
    ('SteamEquipment', 'Design_Level_Calculation_Method'): {
        'EquipmentLevel': 'Design_Level',
        'Watts/Area': 'Power_per_Zone_Floor_Area',
        'Watts/Person': 'Power_per_Person',
        'Power/Area': 'Power_per_Zone_Floor_Area',
        'Power/Person': 'Power_per_Person'},
    ('OtherEquipment', 'Design_Level_Calculation_Method'): {
        'EquipmentLevel': 'Design_Level',
        'Watts/Area': 'Power_per_Zone_Floor_Area',
        'Watts/Person': 'Power_per_Person',
        'Power/Area': 'Power_per_Zone_Floor_Area',
        'Power/Person': 'Power_per_Person'},
    ('ElectricEquipment:ITE:AirCooled', 'Design_Power_Input_Calculation_Method'): {
        'Watts/Unit': 'Watts_per_Unit',
        'Watts/Area': 'Watts_per_Zone_Floor_Area'},
    ('ZoneInfiltration:DesignFlowRate', 'Design_Flow_Rate_Calculation_Method'): {
        'Flow/Zone': 'Design_Flow_Rate',
        'Flow/Area': 'Flow_per_Zone_Floor_Area',
        'Flow/ExteriorArea': 'Flow_per_Exterior_Surface_Area',
        'Flow/ExteriorWallArea': 'Flow_per_Exterior_Surface_Area',
        'AirChanges/Hour': 'Air_Changes_per_Hour'},
    ('ZoneVentilation:DesignFlowRate', 'Design_Flow_Rate_Calculation_Method'): {
        'Flow/Zone': 'Design_Flow_Rate',
        'Flow/Area': 'Flow_Rate_per_Zone_Floor_Area',
        'Flow/Person': 'Flow_Rate_per_Person',
        'AirChanges/Hour': 'Air_Changes_per_Hour'},
    ('ZoneMixing', 'Design_Flow_Rate_Calculation_Method'): {
        'Flow/Zone': 'Design_Flow_Rate',
        'Flow/Area': 'Flow_Rate_per_Zone_Floor_Area',
        'Flow/Person': 'Flow_Rate_per_Person',
        'AirChanges/Hour': 'Air_Changes_per_Hour'},
    ('ZoneCrossMixing', 'Design_Flow_Rate_Calculation_Method'): {
        'Flow/Zone': 'Design_Flow_Rate',
        'Flow/Area': 'Flow_Rate_per_Zone_Floor_Area',
        'Flow/Person': 'Flow_Rate_per_Person',
        'AirChanges/Hour': 'Air_Changes_per_Hour'},
    ('DesignSpecification:OutdoorAir', 'Outdoor_Air_Method'): {
        'Flow/Person': 'Outdoor_Air_Flow_per_Person',
        'Flow/Area': 'Outdoor_Air_Flow_per_Zone_Floor_Area',
        'Flow/Zone': 'Outdoor_Air_Flow_per_Zone',
        'AirChanges/Hour': 'Outdoor_Air_Flow_Air_Changes_per_Hour',
        'Sum': 'sum of Outdoor_Air_Flow_per_Person + Outdoor_Air_Flow_per_Zone_Floor_Area + Outdoor_Air_Flow_per_Zone + Outdoor_Air_Flow_Air_Changes_per_Hour',
        'Maximum': 'maximum of Outdoor_Air_Flow_per_Person, Outdoor_Air_Flow_per_Zone_Floor_Area, Outdoor_Air_Flow_per_Zone, Outdoor_Air_Flow_Air_Changes_per_Hour',
        'IndoorAirQualityProcedure': None,
        'ProportionalControlBasedOnDesignOccupancy': None,
        'ProportionalControlBasedOnOccupancySchedule': None},
    ('Daylighting:Controls', 'Lighting_Control_Type'): {
        'Continuous': 'Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control',
        'ContinuousOff': 'Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control',
        'Stepped': 'Number_of_Stepped_Control_Steps'},
    ('Sizing:Zone', 'Zone_Cooling_Design_Supply_Air_Temperature_Input_Method'): {
        'SupplyAirTemperature': 'Zone_Cooling_Design_Supply_Air_Temperature',
        'TemperatureDifference': 'Zone_Cooling_Design_Supply_Air_Temperature_Difference'},
    ('Sizing:Zone', 'Zone_Heating_Design_Supply_Air_Temperature_Input_Method'): {
        'SupplyAirTemperature': 'Zone_Heating_Design_Supply_Air_Temperature',
        'TemperatureDifference': 'Zone_Heating_Design_Supply_Air_Temperature_Difference'},
    ('Sizing:Zone', 'Cooling_Design_Air_Flow_Method'): {
        'Flow/Zone': 'Cooling_Design_Air_Flow_Rate',
        'DesignDay': None,
        'DesignDayWithLimit': 'Cooling_Minimum_Air_Flow_per_Zone_Floor_Area / Cooling_Minimum_Air_Flow (caps applied to design-day result)'},
    ('Sizing:Zone', 'Heating_Design_Air_Flow_Method'): {
        'Flow/Zone': 'Heating_Design_Air_Flow_Rate',
        'DesignDay': None,
        'DesignDayWithLimit': 'Heating_Maximum_Air_Flow_per_Zone_Floor_Area / Heating_Maximum_Air_Flow (caps applied to design-day result)'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Cooling_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Cooling_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingAirflow': 'Cooling_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FlowPerCoolingCapacity': 'Cooling_Supply_Air_Flow_Rate_Per_Unit_Cooling_Capacity'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'No_Load_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'No_Load_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingAirflow': 'No_Load_Fraction_of_Cooling_Supply_Air_Flow_Rate',
        'FractionOfAutosizedHeatingAirflow': 'No_Load_Fraction_of_Heating_Supply_Air_Flow_Rate'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate_Method'): {
        'None': None,
        'SupplyAirFlowRate': 'Heating_Supply_Air_Flow_Rate',
        'FlowPerFloorArea': 'Heating_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedHeatingAirflow': 'Heating_Fraction_of_Heating_Supply_Air_Flow_Rate',
        'FlowPerHeatingCapacity': 'Heating_Supply_Air_Flow_Rate_Per_Unit_Heating_Capacity'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity_Method'): {
        'None': None,
        'CoolingDesignCapacity': 'Cooling_Design_Capacity',
        'CapacityPerFloorArea': 'Cooling_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedCoolingCapacity': 'Fraction_of_Autosized_Cooling_Design_Capacity'},
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity_Method'): {
        'None': None,
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity'},
    ('Sizing:System', 'Cooling_Supply_Air_Flow_Rate_Method'): {
        'Flow/System': 'Cooling_Supply_Air_Flow_Rate',
        'DesignDay': None,
        'FlowPerFloorArea': 'Cooling_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedCoolingAirflow': 'Cooling_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FlowPerCoolingCapacity': 'Cooling_Supply_Air_Flow_Rate_Per_Unit_Cooling_Capacity'},
    ('Sizing:System', 'Heating_Supply_Air_Flow_Rate_Method'): {
        'Flow/System': 'Heating_Supply_Air_Flow_Rate',
        'DesignDay': None,
        'FlowPerFloorArea': 'Heating_Supply_Air_Flow_Rate_Per_Floor_Area',
        'FractionOfAutosizedHeatingAirflow': 'Heating_Fraction_of_Autosized_Heating_Supply_Air_Flow_Rate',
        'FractionOfAutosizedCoolingAirflow': 'Heating_Fraction_of_Autosized_Cooling_Supply_Air_Flow_Rate',
        'FlowPerHeatingCapacity': 'Heating_Supply_Air_Flow_Rate_Per_Unit_Heating_Capacity'},
    ('Sizing:System', 'Cooling_Design_Capacity_Method'): {
        'None': None,
        'CoolingDesignCapacity': 'Cooling_Design_Capacity',
        'CapacityPerFloorArea': 'Cooling_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedCoolingCapacity': 'Fraction_of_Autosized_Cooling_Design_Capacity'},
    ('Sizing:System', 'Heating_Design_Capacity_Method'): {
        'None': None,
        'HeatingDesignCapacity': 'Heating_Design_Capacity',
        'CapacityPerFloorArea': 'Heating_Design_Capacity_Per_Floor_Area',
        'FractionOfAutosizedHeatingCapacity': 'Fraction_of_Autosized_Heating_Design_Capacity'},
}

AUTOSIZABLE = {
    ('People', 'Sensible_Heat_Fraction'),
    ('ZoneVentilation:WindandStackOpenArea', 'Opening_Effectiveness'),
    ('ZoneVentilation:WindandStackOpenArea', 'Discharge_Coefficient_for_Opening'),
    ('Sizing:Zone', 'Dedicated_Outdoor_Air_Low_Setpoint_Temperature_for_Design'),
    ('Sizing:Zone', 'Dedicated_Outdoor_Air_High_Setpoint_Temperature_for_Design'),
    ('Sizing:System', 'Design_Outdoor_Air_Flow_Rate'),
    ('Sizing:System', 'Central_Heating_Maximum_System_Air_Flow_Ratio'),
    ('Sizing:System', 'Cooling_Design_Capacity'),
    ('Sizing:System', 'Heating_Design_Capacity'),
    ('Sizing:System', 'Occupant_Diversity'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'No_Load_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Supply_Air_Flow_Rate'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Cooling_Design_Capacity'),
    ('DesignSpecification:ZoneHVAC:Sizing', 'Heating_Design_Capacity'),
}

CONSTRAINTS = {
    'People': [
        'Return Air Fraction + Fraction Radiant + Fraction Visible on Lights must not exceed 1.0 (People has an analogous radiant/latent split but no cross-field sum cap).',
        'A thermal comfort schedule listed with no thermal comfort model selected produces a warning and the schedule is reported unused.',
        'AnkleDraftASH55 results are only valid for relative air velocity below 0.2 m/s, metabolic rate below 1.3 met and clothing below 0.7 clo.',
    ],
    'Lights': [
        'Return Air Fraction + Fraction Radiant + Fraction Visible must not exceed 1.0 or EnergyPlus raises an error.',
        'Return Air Fraction = Yes (calculated from plenum temperature) should only be used for recessed, non-vented luminaires.',
        'If Daylighting:Controls is applied to the zone/space, Fraction Replaceable acts as an on/off flag for dimming control and must be 0 (no dimming) or 1 (full dimming).',
    ],
    'OtherEquipment': [
        'Negative values in the Design Level / Power per Area / Power per Person fields represent a heat loss instead of a gain.',
    ],
    'ElectricEquipment:ITE:AirCooled': [
        'Only Zone or Space Name is allowed (no ZoneList/SpaceList), unlike People/Lights/electric-type equipment objects.',
        'FlowControlWithApproachTemperatures is only valid for ITE zones served by a single-duct VAV terminal unit, and other return-air heat gains (windows, lights) are not allowed on that zone when it is used.',
        'For multiple ITE objects in one zone, the same Air Flow Calculation Method should be used for all of them.',
    ],
    'ZoneAirBalance:OutdoorAir': [
        'Cannot be used simultaneously with the AirflowNetwork model; if AirflowNetwork is active, Air Balance Method is reset to None.',
        'Does not combine airflows from Fan:ZoneExhaust objects and is independent of HVAC equipment operation.',
    ],
    'ZoneMixing': [
        'Only affects the energy balance of the receiving zone, not the source zone; a complementary ZoneMixing object must be added to model return flow.',
    ],
    'Daylighting:Controls': [
        'Only one Daylighting Method (SplitFlux or DElight) should be used per zone.',
        'With the DElight method, up to 100 reference points per zone are allowed and the Fraction of Lights/Zone Controlled values across all reference points must sum to 1.0.',
        'A zone multiplier should not be used on a daylit zone whose windows are shadowed by exterior obstructions (trees, neighboring buildings); it is fine for shadowing by overhangs, fins or window setback.',
        'With the SplitFlux method, windows should be entered separately rather than using a window multiplier, or the illuminance calculation will be incorrect.',
        'Neither of two zones sharing a daylit interior window may have an exterior window with Glare Control Is Active = Yes, or with Shading Control Type = MeetDaylightIlluminanceSetpoint.',
    ],
    'DaylightingDevice:Tubular': [
        'Shading control devices, frames/dividers, and multipliers other than 1.0 are not allowed on the dome or diffuser.',
        'Dome, diffuser, and pipe cross-sectional areas must be approximately equal.',
        'Outside face environment objects are not allowed; dome and diffuser constructions cannot be more than one layer.',
    ],
    'DaylightingDevice:Shelf': [
        'The inside shelf surface must have Outside Boundary Condition = Surface (referencing itself) and exactly 4 vertices.',
        'The upper window may not have shading control devices, frames, dividers, or a multiplier other than 1.0.',
        'The outside shelf surface vertices must be ordered so the outward normal points upward.',
    ],
    'DaylightingDevice:LightWell': [
        'Light wells may be assigned to rectangular or triangular exterior windows only, never to interior windows.',
    ],
    'AirflowNetwork:SimulationControl': [
        'AirflowNetwork Control = NoMultizoneOrDistribution runs only the Simple-model objects (ZoneInfiltration:*, ZoneVentilation:*, ZoneMixing, ZoneCrossMixing, ZoneRefrigerationDoorMixing, ZoneAirBalance:OutdoorAir, ZoneEarthtube, ZoneThermalChimney, ZoneCoolTower:Shower).',
        'AirflowNetwork Control = MultizoneWithoutDistribution or MultizoneWithDistribution ignores those same Simple-model objects entirely.',
        'AirflowNetwork Control = MultizoneWithDistributionOnlyDuringFanOperation runs distribution calculations while the system fan is on and Simple calculations while it is off.',
        'If Wind Pressure Coefficient Type = Input, matching AirflowNetwork:MultiZone:WindPressureCoefficientArray, ExternalNode, and WindPressureCoefficientValues objects must be supplied; if SurfaceAverageCalculation, those objects are not used and the method applies only to rectangular buildings.',
    ],
    'AirflowNetwork:MultiZone:Surface': [
        'Do not enter two AirflowNetwork:MultiZone:Surface objects for the two sides of the same interzone surface; it would double-count the airflow.',
        'When Ventilation Control Mode = AdjacentTemperature or AdjacentEnthalpy, the surface must be an interior surface.',
        'If the surface uses Construction:AirBoundary, only Ventilation Control Mode = Constant is valid, and the Venting Availability Schedule is ignored.',
        'For a ZoneExhaustFan leakage component, the surface must be exterior and its zone must match the ZoneHVAC:EquipmentConnections zone of the fan; surface-level ventilation controls are ignored while the fan runs.',
    ],
    'Sizing:Zone': [
        'Zone Heating Design Supply Air Temperature must be greater than Zone Cooling Design Supply Air Temperature.',
        'Design Specification Outdoor Air Object Name may reference either a single DesignSpecification:OutdoorAir object or a DesignSpecification:OutdoorAir:SpaceList for per-space requirements.',
    ],
    'Sizing:Plant': [
        'Sizing Option = Coincident additionally requires SimulationControl field "Do HVAC Sizing Simulation for Sizing Periods" = Yes.',
    ],
}

SECTIONS_READ = [
    'group-internal-gains-people-lights-other',
    'group-daylighting',
    'group-exterior-energy-use-equipment',
    'group-airflow',
    'group-airflow-network',
    'group-design-objects',
]

IDD_DISAGREEMENTS = [
    "People: docs prose calls the Area/Person field 'Zone Floor Area per Person'; the IDD field is actually named 'Floor Area per Person' (Floor_Area_per_Person). IDD spelling used.",
    "People: docs prose calls the People/Area field 'the number to apply... Value * Floor Area'; IDD field name is 'People per Floor Area' (People_per_Floor_Area), matches prose intent but exact IDD name used.",
    "GasEquipment/HotWaterEquipment/SteamEquipment/OtherEquipment: docs describe the per-area/per-person fields as 'Power per Zone Floor Area'/'Power per Person' while also listing legacy key aliases 'Watts/Area'/'Watts/Person' alongside 'Power/Area'/'Power/Person' -- both key spellings are present in the IDD choice list; field names use 'Power_per_...' per IDD, not 'Watts_per_...'.",
]
