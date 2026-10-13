"""Rules from: Group - Simulation Parameters, Group - Compliance Objects,
Group - Location - Climate - Weather File Access, Group - Advanced Surface Concepts,
Group - Detailed Ground Heat Transfer, Group - Room Air Models.
EnergyPlus 9.6 Input Output Reference (https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/).
Field names verified against C:/EnergyPlusV9-6-0/Energy+.idd.
"""

GATED = {
    # --- SimulationControl ---
    ('SimulationControl', 'Maximum_Number_of_HVAC_Sizing_Simulation_Passes'): {
        'by': 'Do_HVAC_Sizing_Simulation_for_Sizing_Periods', 'when': ('Yes',),
        'note': 'Optional and only used if Do_HVAC_Sizing_Simulation_for_Sizing_Periods = Yes.'},

    # --- ShadowCalculation ---
    ('ShadowCalculation', 'Shading_Calculation_Update_Frequency'): {
        'by': 'Shading_Calculation_Update_Frequency_Method', 'when': ('Periodic',),
        'note': 'Number of days between recalculations; only used if the update frequency method is Periodic (ignored, and detailed timestep recalculation is used instead, when method = Timestep).'},
    ('ShadowCalculation', 'Sky_Diffuse_Modeling_Algorithm'): {
        'by': 'Shading_Calculation_Update_Frequency_Method', 'when': ('Periodic',),
        'note': "Selects Simple vs Detailed sky diffuse modeling for the Periodic update method; when Shading_Calculation_Update_Frequency_Method = Timestep the program always uses DetailedSkyDiffuseModeling regardless of this field's value."},
    ('ShadowCalculation', 'Polygon_Clipping_Algorithm'): {
        'by': 'Shading_Calculation_Method', 'when': ('PolygonClipping',),
        'note': 'Advanced feature selecting the clipping algorithm used only by the CPU-based PolygonClipping shading method; has no effect for PixelCounting, Scheduled or Imported.'},
    ('ShadowCalculation', 'Pixel_Counting_Resolution'): {
        'by': 'Shading_Calculation_Method', 'when': ('PixelCounting',),
        'note': 'Rendering resolution used only by the GPU-based PixelCounting shading method.'},
    ('ShadowCalculation', 'Shading_Zone_Group_1_ZoneList_Name'): {
        'by': 'Disable_Self_Shading_Within_Shading_Zone_Groups', 'when': ('Yes',),
        'note': 'At least one Shading_Zone_Group_<n>_ZoneList_Name must be specified when either Disable_Self_Shading_Within_Shading_Zone_Groups or Disable_Self_Shading_From_Shading_Zone_Groups_to_Other_Zones = Yes; otherwise these zone-group fields are ignored. (Both switches gate the same group-name fields; only one is modeled as the "by" field here.)'},

    # --- ZoneAirContaminantBalance ---
    ('ZoneAirContaminantBalance', 'Outdoor_Carbon_Dioxide_Schedule_Name'): {
        'by': 'Carbon_Dioxide_Concentration', 'when': ('Yes',),
        'note': 'Only used if Carbon_Dioxide_Concentration = Yes (CO2 simulation performed).'},
    ('ZoneAirContaminantBalance', 'Outdoor_Generic_Contaminant_Schedule_Name'): {
        'by': 'Generic_Contaminant_Concentration', 'when': ('Yes',),
        'note': 'Only used if Generic_Contaminant_Concentration = Yes (generic contaminant simulation performed).'},

    # --- SizingPeriod:DesignDay ---
    ('SizingPeriod:DesignDay', 'Dry_Bulb_Temperature_Range_Modifier_Day_Schedule_Name'): {
        'by': 'Dry_Bulb_Temperature_Range_Modifier_Type',
        'when': ('MultiplierSchedule', 'DifferenceSchedule', 'TemperatureProfileSchedule'),
        'note': 'Not used when Dry_Bulb_Temperature_Range_Modifier_Type = DefaultMultipliers (the ASHRAE default profile is used instead).'},
    ('SizingPeriod:DesignDay', 'Wetbulb_or_DewPoint_at_Maximum_Dry_Bulb'): {
        'by': 'Humidity_Condition_Type',
        'when': ('WetBulb', 'DewPoint', 'WetBulbProfileDefaultMultipliers',
                 'WetBulbProfileMultiplierSchedule', 'WetBulbProfileDifferenceSchedule'),
        'note': 'Unused for HumidityRatio, Enthalpy or RelativeHumiditySchedule condition types.'},
    ('SizingPeriod:DesignDay', 'Humidity_Condition_Day_Schedule_Name'): {
        'by': 'Humidity_Condition_Type',
        'when': ('RelativeHumiditySchedule', 'WetBulbProfileMultiplierSchedule', 'WetBulbProfileDifferenceSchedule'),
        'note': 'Only used for the three schedule-driven humidity condition types.'},
    ('SizingPeriod:DesignDay', 'Humidity_Ratio_at_Maximum_Dry_Bulb'): {
        'by': 'Humidity_Condition_Type', 'when': ('HumidityRatio',),
        'note': 'Required only if Humidity_Condition_Type = HumidityRatio.'},
    ('SizingPeriod:DesignDay', 'Enthalpy_at_Maximum_Dry_Bulb'): {
        'by': 'Humidity_Condition_Type', 'when': ('Enthalpy',),
        'note': 'Required only if Humidity_Condition_Type = Enthalpy.'},
    ('SizingPeriod:DesignDay', 'Daily_Wet_Bulb_Temperature_Range'): {
        'by': 'Humidity_Condition_Type', 'when': ('WetBulbProfileDefaultMultipliers', 'WetBulbProfileMultiplierSchedule'),
        'note': 'Required only for the wet-bulb-profile humidity condition types.'},
    ('SizingPeriod:DesignDay', 'Beam_Solar_Day_Schedule_Name'): {
        'by': 'Solar_Model_Indicator', 'when': ('Schedule',),
        'note': 'Only used if Solar_Model_Indicator = Schedule.'},
    ('SizingPeriod:DesignDay', 'Diffuse_Solar_Day_Schedule_Name'): {
        'by': 'Solar_Model_Indicator', 'when': ('Schedule',),
        'note': 'Only used if Solar_Model_Indicator = Schedule.'},
    ('SizingPeriod:DesignDay', 'ASHRAE_Clear_Sky_Optical_Depth_for_Beam_Irradiance_(taub)'): {
        'by': 'Solar_Model_Indicator', 'when': ('ASHRAETau', 'ASHRAETau2017'),
        'note': 'Required (and only used) if Solar_Model_Indicator = ASHRAETau or ASHRAETau2017.'},
    ('SizingPeriod:DesignDay', 'ASHRAE_Clear_Sky_Optical_Depth_for_Diffuse_Irradiance_(taud)'): {
        'by': 'Solar_Model_Indicator', 'when': ('ASHRAETau', 'ASHRAETau2017'),
        'note': 'Required (and only used) if Solar_Model_Indicator = ASHRAETau or ASHRAETau2017.'},
    ('SizingPeriod:DesignDay', 'Sky_Clearness'): {
        'by': 'Solar_Model_Indicator', 'when': ('ASHRAEClearSky', 'ZhangHuang'),
        'note': 'Used only if Solar_Model_Indicator = ASHRAEClearSky or ZhangHuang.'},

    # --- WeatherProperty:SkyTemperature ---
    ('WeatherProperty:SkyTemperature', 'Schedule_Name'): {
        'by': 'Calculation_Type',
        'when': ('ScheduleValue', 'DifferenceScheduleDryBulbValue', 'DifferenceScheduleDewPointValue'),
        'note': 'Required only if Calculation_Type is one of the three schedule-driven types; unused for the model-based types (ClarkAllen, Brunt, Idso, BerdahlMartin).'},

    # --- SurfaceProperty:OtherSideCoefficients ---
    ('SurfaceProperty:OtherSideCoefficients', 'Constant_Temperature_Coefficient'): {
        'by': 'Sinusoidal_Variation_of_Constant_Temperature_Coefficient', 'when': ('No',),
        'note': 'Ignored if Sinusoidal_Variation_of_Constant_Temperature_Coefficient = Yes.'},
    ('SurfaceProperty:OtherSideCoefficients', 'Period_of_Sinusoidal_Variation'): {
        'by': 'Sinusoidal_Variation_of_Constant_Temperature_Coefficient', 'when': ('Yes',),
        'note': 'Only used to define the time period when sinusoidal variation is active.'},

    # --- SurfaceProperty:ExposedFoundationPerimeter ---
    ('SurfaceProperty:ExposedFoundationPerimeter', 'Total_Exposed_Perimeter'): {
        'by': 'Exposed_Perimeter_Calculation_Method', 'when': ('TotalExposedPerimeter',),
        'note': 'Only used when Exposed_Perimeter_Calculation_Method = TotalExposedPerimeter.'},
    ('SurfaceProperty:ExposedFoundationPerimeter', 'Exposed_Perimeter_Fraction'): {
        'by': 'Exposed_Perimeter_Calculation_Method', 'when': ('ExposedPerimeterFraction',),
        'note': 'Only used when Exposed_Perimeter_Calculation_Method = ExposedPerimeterFraction.'},
    ('SurfaceProperty:ExposedFoundationPerimeter', 'Surface_Segment_1_Exposed'): {
        'by': 'Exposed_Perimeter_Calculation_Method', 'when': ('BySegment',),
        'note': 'The Surface_Segment_<n>_Exposed fields are only used when Exposed_Perimeter_Calculation_Method = BySegment; the number of segments must match the number of vertices of the corresponding floor surface.'},

    # --- RoomAirModelType ---
    ('RoomAirModelType', 'Air_Temperature_Coupling_Strategy'): {
        'by': 'Room_Air_Modeling_Type', 'when': ('OneNodeDisplacementVentilation',),
        'note': 'Only used by the OneNodeDisplacementVentilation (Mundt) model; the UCSD displacement, cross-ventilation and UFAD models ignore this field and always use direct coupling.'},

    # --- RoomAir:TemperaturePattern:TwoGradient ---
    ('RoomAir:TemperaturePattern:TwoGradient', 'Upper_Temperature_Bound'): {
        'by': 'Gradient_Interpolation_Mode',
        'when': ('OutdoorDryBulbTemperature', 'ZoneDryBulbTemperature', 'ZoneAndOutdoorTemperatureDifference'),
        'note': 'Temperature-based bounds are only used for the three temperature-driven interpolation modes; the load-driven modes use the Heat Rate bound fields instead.'},
    ('RoomAir:TemperaturePattern:TwoGradient', 'Lower_Temperature_Bound'): {
        'by': 'Gradient_Interpolation_Mode',
        'when': ('OutdoorDryBulbTemperature', 'ZoneDryBulbTemperature', 'ZoneAndOutdoorTemperatureDifference'),
        'note': 'Temperature-based bounds are only used for the three temperature-driven interpolation modes.'},
    ('RoomAir:TemperaturePattern:TwoGradient', 'Upper_Heat_Rate_Bound'): {
        'by': 'Gradient_Interpolation_Mode', 'when': ('SensibleCoolingLoad', 'SensibleHeatingLoad'),
        'note': 'Only used for the two load-driven interpolation modes.'},
    ('RoomAir:TemperaturePattern:TwoGradient', 'Lower_Heat_Rate_Bound'): {
        'by': 'Gradient_Interpolation_Mode', 'when': ('SensibleCoolingLoad', 'SensibleHeatingLoad'),
        'note': 'Only used for the two load-driven interpolation modes.'},

    # --- RoomAirSettings:UnderFloorAirDistributionInterior / Exterior ---
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_A'): {
        'by': 'Floor_Diffuser_Type', 'when': ('Custom',),
        'note': 'Coefficients A-E of the Kc formula are only user-supplied when Floor_Diffuser_Type = Custom; for Swirl, VariableArea, HorizontalSwirl and LinearBarGrille they are autocalculated from built-in per-type defaults and any value entered is not used unless the diffuser type is Custom.'},
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_A'): {
        'by': 'Floor_Diffuser_Type', 'when': ('Custom',),
        'note': 'Same Custom-only behavior as the Interior UFAD object.'},
}

METHOD_GROUPS = {
    ('SizingPeriod:DesignDay', 'Humidity_Condition_Type'): {
        'WetBulb': 'Wetbulb_or_DewPoint_at_Maximum_Dry_Bulb',
        'DewPoint': 'Wetbulb_or_DewPoint_at_Maximum_Dry_Bulb',
        'HumidityRatio': 'Humidity_Ratio_at_Maximum_Dry_Bulb',
        'Enthalpy': 'Enthalpy_at_Maximum_Dry_Bulb',
        'RelativeHumiditySchedule': 'Humidity_Condition_Day_Schedule_Name',
        'WetBulbProfileMultiplierSchedule': 'Humidity_Condition_Day_Schedule_Name',
        'WetBulbProfileDifferenceSchedule': 'Humidity_Condition_Day_Schedule_Name',
        'WetBulbProfileDefaultMultipliers': 'Wetbulb_or_DewPoint_at_Maximum_Dry_Bulb',
    },
    ('SizingPeriod:DesignDay', 'Dry_Bulb_Temperature_Range_Modifier_Type'): {
        'DefaultMultipliers': None,
        'MultiplierSchedule': 'Dry_Bulb_Temperature_Range_Modifier_Day_Schedule_Name',
        'DifferenceSchedule': 'Dry_Bulb_Temperature_Range_Modifier_Day_Schedule_Name',
        'TemperatureProfileSchedule': 'Dry_Bulb_Temperature_Range_Modifier_Day_Schedule_Name',
    },
    ('SizingPeriod:DesignDay', 'Solar_Model_Indicator'): {
        'ASHRAEClearSky': 'Sky_Clearness',
        'ZhangHuang': 'Sky_Clearness',
        'Schedule': ('Beam_Solar_Day_Schedule_Name', 'Diffuse_Solar_Day_Schedule_Name'),
        'ASHRAETau': ('ASHRAE_Clear_Sky_Optical_Depth_for_Beam_Irradiance_(taub)',
                       'ASHRAE_Clear_Sky_Optical_Depth_for_Diffuse_Irradiance_(taud)'),
        'ASHRAETau2017': ('ASHRAE_Clear_Sky_Optical_Depth_for_Beam_Irradiance_(taub)',
                           'ASHRAE_Clear_Sky_Optical_Depth_for_Diffuse_Irradiance_(taud)'),
    },
    ('WeatherProperty:SkyTemperature', 'Calculation_Type'): {
        'ClarkAllen': None, 'Brunt': None, 'Idso': None, 'BerdahlMartin': None,
        'ScheduleValue': 'Schedule_Name',
        'DifferenceScheduleDryBulbValue': 'Schedule_Name',
        'DifferenceScheduleDewPointValue': 'Schedule_Name',
    },
    ('ShadowCalculation', 'Shading_Calculation_Method'): {
        'PolygonClipping': 'Polygon_Clipping_Algorithm',
        'PixelCounting': 'Pixel_Counting_Resolution',
        'Scheduled': None,   # requires an External_Shading_Fraction_Schedule_Name on SurfaceProperty:LocalEnvironment (separate object)
        'Imported': None,    # requires a Schedule:File:Shading object (separate object)
    },
    ('SurfaceProperty:ExposedFoundationPerimeter', 'Exposed_Perimeter_Calculation_Method'): {
        'TotalExposedPerimeter': 'Total_Exposed_Perimeter',
        'ExposedPerimeterFraction': 'Exposed_Perimeter_Fraction',
        'BySegment': 'Surface_Segment_1_Exposed',  # plus Surface_Segment_2..21_Exposed
    },
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Floor_Diffuser_Type'): {
        'Swirl': None, 'VariableArea': None, 'HorizontalSwirl': None, 'LinearBarGrille': None,
        'Custom': ('Coefficient_A', 'Coefficient_B', 'Coefficient_C', 'Coefficient_D', 'Coefficient_E'),
    },
    ('RoomAirModelType', 'Room_Air_Modeling_Type'): {
        'Mixing': None,
        'UserDefined': 'RoomAir:TemperaturePattern:UserDefined',
        'OneNodeDisplacementVentilation': 'RoomAirSettings:OneNodeDisplacementVentilation',
        'ThreeNodeDisplacementVentilation': 'RoomAirSettings:ThreeNodeDisplacementVentilation',
        'CrossVentilation': 'RoomAirSettings:CrossVentilation',
        'UnderFloorAirDistributionInterior': 'RoomAirSettings:UnderFloorAirDistributionInterior',
        'UnderFloorAirDistributionExterior': 'RoomAirSettings:UnderFloorAirDistributionExterior',
        'AirflowNetwork': 'RoomAirSettings:AirflowNetwork',
    },
}

AUTOSIZABLE = {
    ('Foundation:Kiva:Settings', 'Deep_Ground_Depth'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Number_of_Diffusers'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Power_per_Plume'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Design_Effective_Area_of_Diffuser'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Diffuser_Slot_Angle_from_Vertical'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Transition_Height'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_A'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_B'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_C'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_D'),
    ('RoomAirSettings:UnderFloorAirDistributionInterior', 'Coefficient_E'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Number_of_Diffusers'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Power_per_Plume'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Design_Effective_Area_of_Diffuser'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Diffuser_Slot_Angle_from_Vertical'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Transition_Height'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_A'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_B'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_C'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_D'),
    ('RoomAirSettings:UnderFloorAirDistributionExterior', 'Coefficient_E'),
}

CONSTRAINTS = {
    'SimulationControl': [
        'Only one SimulationControl object is permitted per input file.',
        'Do_System_Sizing_Calculation = Yes requires Do_Zone_Sizing_Calculation = Yes in the same run, or the program raises an error; zone sizing arrays must be filled to perform system sizing.',
        'Plant sizing (Do_Plant_Sizing_Calculation) can be requested independently, without also requesting Zone or System sizing.',
    ],
    'Building': [
        'Solar_Distribution = FullInteriorAndExterior or FullInteriorAndExteriorWithReflections requires that every zone be convex and that its surfaces fully enclose the zone volume; otherwise use FullExterior (or FullExteriorWithReflections) instead.',
    ],
    'Timestep': [
        'Number_of_Timesteps_per_Hour must divide evenly into 60; allowed values are 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30 and 60.',
    ],
    'ConvergenceLimits': [
        'Minimum_System_Timestep of 0 sets the minimum HVAC timestep to the Zone Timestep (from Timestep); values above the zone timestep (in minutes) are effectively clamped to it.',
        'Maximum_Plant_Iterations must exceed Minimum_Plant_Iterations for the plant solver to have room to iterate.',
    ],
    'ShadowCalculation': [
        'Shading_Calculation_Method = Scheduled requires an External_Shading_Fraction_Schedule_Name entered on a SurfaceProperty:LocalEnvironment object for each exterior surface that needs it; surfaces without one get no shading.',
        'Shading_Calculation_Method = Imported requires a Schedule:File:Shading object; surfaces not listed in that file get no shading.',
        'If PixelCounting is selected and GPU hardware (or emulation) is unavailable, EnergyPlus warns and reverts to PolygonClipping.',
        'Sky_Diffuse_Modeling_Algorithm is forced to DetailedSkyDiffuseModeling whenever Shading_Calculation_Update_Frequency_Method = Timestep, overriding whatever value is entered.',
    ],
    'HeatBalanceAlgorithm': [
        'Algorithm = ConductionFiniteDifference activates the separate HeatBalanceSettings:ConductionFiniteDifference object; that object has no effect unless Algorithm is set to ConductionFiniteDifference.',
        'Algorithm = MoisturePenetrationDepthConductionTransferFunction requires a MaterialProperty:MoisturePenetrationDepth:Settings object on the relevant material(s), or that material behaves as if EMPD were not active.',
        'Algorithm = CombinedHeatAndMoistureFiniteElement (HAMT) requires the HAMT-specific material property objects (e.g. MaterialProperty:HeatAndMoistureTransfer:*) on the relevant materials.',
    ],
    'ZoneCapacitanceMultiplier:ResearchSpecial': [
        'If Zone_or_ZoneList_Name is left blank, the multipliers apply to all zones not otherwise covered by a more specific ZoneCapacitanceMultiplier:ResearchSpecial object.',
    ],
    'RunPeriod': [
        'End_Year, if specified, must be after Begin_Year.',
        'If Treat_Weather_as_Actual = Yes, leap days must be present in the weather file/run period as appropriate for the actual calendar.',
        'Multiple RunPeriod objects may be input but their date ranges may not overlap.',
    ],
    'Site:GroundTemperature:BuildingSurface': [
        'Only one instance of this object is allowed; its 12 monthly values are used as the outside surface temperature for every surface whose Outside_Boundary_Condition = Ground.',
    ],
    'Site:GroundTemperature:Shallow': [
        'Only one Site:GroundTemperature:Shallow object is allowed.',
    ],
    'Site:GroundTemperature:Deep': [
        'Only one Site:GroundTemperature:Deep object is allowed.',
    ],
    'Site:WeatherStation': [
        'If this object is omitted, WMO standard measurement-height conditions are assumed for translating weather-file wind speed to building height.',
    ],
    'Site:HeightVariation': [
        'When present, this object overrides the wind-speed profile implied by the Building object Terrain field, even if its own wind-speed fields are left blank.',
        'Wind_Speed_Profile_Exponent = 0 turns off wind-speed dependence on height; Air_Temperature_Gradient_Coefficient = 0 turns off temperature dependence on height.',
    ],
    'SurfaceControl:MovableInsulation': [
        'Applies only to opaque, regular surfaces (walls, floors, roofs); it cannot be applied to a subsurface such as a window or door.',
        'A transparent Material_Name is only valid when Insulation_Type = Outside.',
    ],
    'Foundation:Kiva': [
        'Only floor and wall surfaces may reference a Foundation:Kiva object.',
        'Each floor surface must reference a distinct Foundation:Kiva object; any number of wall surfaces may share one Foundation:Kiva object as long as it is referenced by exactly one floor.',
        'Every floor surface with a Foundation:Kiva boundary condition must also have a corresponding SurfaceProperty:ExposedFoundationPerimeter object.',
        'The Interior/Exterior Horizontal/Vertical insulation Depth and Width fields only matter when the corresponding *_Insulation_Material_Name field is filled in; Footing_Depth only matters when Footing_Material_Name is filled in; each Custom_Block_<n>_Depth/X_Position/Z_Position only matters when the corresponding Custom_Block_<n>_Material_Name is filled in.',
    ],
    'Foundation:Kiva:Settings': [
        'Deep_Ground_Boundary_Condition = Autoselect picks ZeroFlux or GroundWater automatically based on site elevation; the explicit ZeroFlux/GroundWater keys force one behavior regardless of elevation.',
    ],
    'SurfaceProperty:OtherSideCoefficients': [
        'Combined_Convective/Radiative_Film_Coefficient > 0 switches the object to compute an outdoor air temperature and then a surface temperature from that film coefficient; <= 0 switches it to compute the outside surface temperature directly from the remaining coefficient fields.',
        'Constant_Temperature_Schedule_Name overrides Constant_Temperature when supplied, and cannot be combined with Sinusoidal_Variation_of_Constant_Temperature_Coefficient = Yes.',
    ],
    'SurfaceConvectionAlgorithm:Inside:AdaptiveModelSelections': [
        'For each convection category, the paired User_Curve_Name field is only used when that category\'s Equation_Source field is set to UserCurve.',
    ],
    'SurfaceConvectionAlgorithm:Outside:AdaptiveModelSelections': [
        'For each convection category, the paired User_Curve_Name field is only used when that category\'s Equation_Source field is set to UserCurve.',
    ],
    'GroundHeatTransfer:Control': [
        'Run_Basement_Preprocessor = Yes/No gates whether the associated GroundHeatTransfer:Basement:* input objects are ever processed; both flags default to No.',
        'Run_Slab_Preprocessor = Yes/No gates whether the associated GroundHeatTransfer:Slab:* input objects are ever processed; both flags default to No.',
    ],
    'RoomAirModelType': [
        'Only one RoomAirModelType object can be specified per zone; the model cannot be switched during a simulation.',
        'The UCSD Displacement, Cross Ventilation and UFAD models automatically fall back from displacement to well-mixed behavior when operating conditions do not support unmixed flow, independent of the Room_Air_Modeling_Type selection.',
    ],
    'RoomAir:Node': [
        'At most 20 (fields Surface_1_Name..Surface_20_Name, plus Surface_21_Name) surfaces may interact with a single air node, and each surface should couple to no more than one node.',
        'Only node types that exchange convective heat with surfaces need any Surface_<n>_Name entries; other node types leave them blank.',
    ],
    'RoomAirSettings:ThreeNodeDisplacementVentilation': [
        'Intended for spaces with low-velocity floor-level displacement ventilation where the dominant heat gains are people and localized sources; use with caution in zones with large heat gains/losses through exterior walls/windows or considerable direct solar gain.',
    ],
    'RoomAirSettings:UnderFloorAirDistributionInterior': [
        'Intended for interior zones served by underfloor air distribution with dominant gains from people/equipment; use with caution where exterior wall/window or solar gains are large.',
    ],
    'RoomAirSettings:UnderFloorAirDistributionExterior': [
        'Intended for exterior zones served by underfloor air distribution, additionally accounting for convective gain from a warm window.',
    ],
    'RoomAirSettings:CrossVentilation': [
        'Used together with the AirflowNetwork natural-ventilation model; distinguishes a jet region and a recirculation region, each with its own characteristic temperature.',
    ],
}

SECTIONS_READ = [
    'group-simulation-parameters',
    'group-compliance-objects',
    'group-location-climate-weather-file-access',
    'group-advanced-surface-concepts',
    'group-detailed-ground-heat-transfer',
    'group-room-air-models',
]

IDD_DISAGREEMENTS = [
    'RoomAirSettings:UnderFloorAirDistributionInterior/Exterior: the Input Output Reference prose refers to the diffuser-type selector simply as "Diffuser Type", but the Energy+.idd field name (A2) is "Floor Diffuser Type".',
    'SizingPeriod:DesignDay Humidity Condition Type: the Input Output Reference prose sometimes writes the key as "Dewpoint" (lower-case p); the Energy+.idd key is spelled "DewPoint".',
    'RoomAir:Node: the Input Output Reference prose says "at most 20 surfaces are allowed to interact with a single air node", but Energy+.idd actually defines 21 extensible Surface <n> Name fields (Surface 1 Name .. Surface 21 Name) for this object.',
]
