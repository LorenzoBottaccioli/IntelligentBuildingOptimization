from config import db

class edd_Actuator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Component_Unique_Name = db.Column(db.String(256), nullable=False)
    Component_Type = db.Column(db.String(256), nullable=False)
    Control_Type = db.Column(db.String(256), nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "componentUniqueName": self.Component_Unique_Name,
            "componentType": self.Component_Type,
            "controlType": self.Control_Type
        }

class rdd_Variable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Var_Type = db.Column(db.String(256), nullable=False)
    Variable_Name = db.Column(db.String(256), nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "varType": self.Var_Type,
            "variableName": self.Variable_Name
        }
    
class current_runperiod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Begin_Month = db.Column(db.String(256), nullable=False)
    Begin_Day_of_Month = db.Column(db.String(256), nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "beginMonth": self.Begin_Month,
            "beginDayOfMonth": self.Begin_Day_of_Month
        }
        

    
class current_output_variable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Key_Value = db.Column(db.String(256), nullable=False)
    Variable_Name = db.Column(db.String(256), nullable=False)
    Reporting_Frequency = db.Column(db.String(256), nullable=False)
    Schedule_Name = db.Column(db.String(256), nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "keyValue": self.Key_Value,
            "variableName": self.Variable_Name,
            "reportingFrequency": self.Reporting_Frequency,
            'scheduleName': self.Schedule_Name
        }
    
class existing_shedule_type_limit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(256), nullable=True)
    Lower_Limit_Value = db.Column(db.String(256), nullable=False)
    Upper_Limit_Value = db.Column(db.String(256), nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "lowerLimitValue": self.Lower_Limit_Value,
            "upperLimitValue": self.Upper_Limit_Value
        }
    
class existing_schedule_name(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Schedule_Name =  db.Column(db.String(256), nullable=True)

    def to_json(self):
        return {
            "id": self.id,
            "scheduleName" : self.Schedule_Name
        }

class current_ems_sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=True)
    OutputVariable_or_OutputMeter_Index_Key_Name = db.Column(db.String, nullable=False)
    OutputVariable_or_OutputMeter_Name = db.Column(db.String, nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "outputVariableOrOutputMeterIndexKeyName": self.OutputVariable_or_OutputMeter_Index_Key_Name,
            "outputVariableOrOutputMeterName": self.OutputVariable_or_OutputMeter_Name
        }
    
class current_ems_actuator(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     Name = db.Column(db.String, nullable=True)
     Actuated_Component_Unique_Name = db.Column(db.String, nullable=False)
     Actuated_Component_Type = db.Column(db.String, nullable=False)
     Actuated_Component_Control_Type = db.Column(db.String, nullable=False)

     def to_json(self):
         return {
             "id": self.id,
             "name": self.Name,
             "actuatedComponentUniqueName": self.Actuated_Component_Unique_Name,
             "actuatedComponentType": self.Actuated_Component_Type,
             "actuatedComponentControlType": self.Actuated_Component_Control_Type
         }
     
class CurrentEMSProgram(db.Model):
    __tablename__ = 'current_ems_programs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    program_lines = db.relationship('ProgramLine', back_populates='current_ems_program', cascade='all, delete-orphan')

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "programLines": [line.line_text for line in self.program_lines]
        }

class ProgramLine(db.Model):
    __tablename__ = 'program_lines'

    id = db.Column(db.Integer, primary_key=True)
    line_text = db.Column(db.String, nullable=False)
    ems_program_id = db.Column(db.Integer, db.ForeignKey('current_ems_programs.id'), nullable=False)
    current_ems_program = db.relationship('CurrentEMSProgram', back_populates='program_lines')

    def to_json(self):
        return {
            "id": self.id,
            "lineText": self.line_text
        }

class CurrentEMSProgramCallingManager(db.Model):
    __tablename__ = 'current_ems_program_calling_managers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    energy_plus_model_calling_point = db.Column(db.String, nullable=False)
    program_names = db.relationship('ProgramName', back_populates='ems_manager', cascade='all, delete-orphan')

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "energyPlusModelCallingPoint": self.energy_plus_model_calling_point,
            "programNames": [name.line_text for name in self.program_names]
        }

class ProgramName(db.Model):
    __tablename__ = 'program_names'

    id = db.Column(db.Integer, primary_key=True)
    line_text = db.Column(db.String, nullable=False)
    ems_manager_id = db.Column(db.Integer, db.ForeignKey('current_ems_program_calling_managers.id'), nullable=False)
    ems_manager = db.relationship('CurrentEMSProgramCallingManager', back_populates='program_names')

    def to_json(self):
        return {
            "id": self.id,
            "lineText": self.line_text
        }

class current_fmu_actuator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=True)
    Actuated_Component_Unique_Name = db.Column(db.String, nullable=False)
    Actuated_Component_Type = db.Column(db.String, nullable=False)
    Actuated_Component_Control_Type = db.Column(db.String, nullable=False)
    FMU_Variable_Name = db.Column(db.String, nullable=True)
    Initial_Value = db.Column(db.String, nullable=False)

    def to_json(self):
         return {
             "id": self.id,
             "name": self.Name,
             "actuatedComponentUniqueName": self.Actuated_Component_Unique_Name,
             "actuatedComponentType": self.Actuated_Component_Type,
             "actuatedComponentControlType": self.Actuated_Component_Control_Type,
             "fmuVariableName": self.FMU_Variable_Name,
             "initialValue": self.Initial_Value
         }
    
class current_fmu_from_variable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    OutputVariable_Index_Key_Name = db.Column(db.String, nullable=False)
    OutputVariable_Name = db.Column(db.String, nullable=False)
    FMU_Variable_Name = db.Column(db.String, nullable=True)

    def to_json(self):
        return {
            "id": self.id,
            "outputVariableIndexKeyName": self.OutputVariable_Index_Key_Name,
            "outputVariableName": self.OutputVariable_Name,
            "fmuVariableName": self.FMU_Variable_Name
        }
    
class current_fmu_to_variable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=True)
    FMU_Variable_Name = db.Column(db.String, nullable=True)
    Initial_Value = db.Column(db.String, nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "fmuVariableName": self.FMU_Variable_Name,
            "initialValue": self.Initial_Value
        }
    
class current_fmu_schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Schedule_Name = db.Column(db.String, nullable=True)
    Schedule_Type_Limits_Names = db.Column(db.String, nullable=False)
    FMU_Variable_Name = db.Column(db.String, nullable=True)
    Initial_Value = db.Column(db.String, nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "scheduleName": self.Schedule_Name,
            "scheduleTypeLimitsNames": self.Schedule_Type_Limits_Names,
            "fmuVariableName": self.FMU_Variable_Name,
            "initialValue": self.Initial_Value
        }
    
class idf_Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Roughness = db.Column(db.String, nullable=False)
    Thickness = db.Column(db.String, nullable=False)
    Conductivity = db.Column(db.String, nullable=False)
    Density = db.Column(db.String, nullable=False)
    Specific_Heat = db.Column(db.String, nullable=False)
    Thermal_Absorptance = db.Column(db.String, nullable=False)
    Solar_Absorptance = db.Column(db.String, nullable=False)
    Visible_Absorptance = db.Column(db.String, nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "roughness": self.Roughness,
            "thickness": self.Thickness,
            "conductivity": self.Conductivity,
            "density": self.Density,
            "specificHeat": self.Specific_Heat,
            "thermalAbsorptance": self.Thermal_Absorptance,
            "solarAbsorptance": self.Solar_Absorptance,
            "visibleAbsorptance": self.Visible_Absorptance
        }

class idf_Construction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Outside_Layer = db.Column(db.String, nullable=False)
    Layer_2 = db.Column(db.String, nullable=True)
    Layer_3 = db.Column(db.String, nullable=True)
    Layer_4 = db.Column(db.String, nullable=True)
    Layer_5 = db.Column(db.String, nullable=True)
    Layer_6 = db.Column(db.String, nullable=True)
    Layer_7 = db.Column(db.String, nullable=True)
    Layer_8 = db.Column(db.String, nullable=True)
    Layer_9 = db.Column(db.String, nullable=True)
    Layer_10 = db.Column(db.String, nullable=True)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "outsideLayer": self.Outside_Layer,
            "layers": [
                self.Outside_Layer,
                self.Layer_2,
                self.Layer_3,
                self.Layer_4,
                self.Layer_5,
                self.Layer_6,
                self.Layer_7,
                self.Layer_8,
                self.Layer_9,
                self.Layer_10
            ]
        }

class idf_FenestrationSurfaceDetailed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Surface_Type = db.Column(db.String, nullable=False)
    Construction_Name = db.Column(db.String, nullable=False)
    Building_Surface_Name = db.Column(db.String, nullable=False)
    Outside_Boundary_Condition_Object = db.Column(db.String, nullable=False)
    View_Factor_to_Ground = db.Column(db.String, nullable=False)
    Frame_and_Divider_Name = db.Column(db.String, nullable=True)
    Multiplier = db.Column(db.String, nullable=False)
    Number_of_Vertices = db.Column(db.String, nullable=False)
    # Coordinates for up to 4 vertices
    Vertex_1_X = db.Column(db.String, nullable=True)
    Vertex_1_Y = db.Column(db.String, nullable=True)
    Vertex_1_Z = db.Column(db.String, nullable=True)
    Vertex_2_X = db.Column(db.String, nullable=True)
    Vertex_2_Y = db.Column(db.String, nullable=True)
    Vertex_2_Z = db.Column(db.String, nullable=True)
    Vertex_3_X = db.Column(db.String, nullable=True)
    Vertex_3_Y = db.Column(db.String, nullable=True)
    Vertex_3_Z = db.Column(db.String, nullable=True)
    Vertex_4_X = db.Column(db.String, nullable=True)
    Vertex_4_Y = db.Column(db.String, nullable=True)
    Vertex_4_Z = db.Column(db.String, nullable=True)

    def to_json(self):
        verts = []
        try:
            count = int(self.Number_of_Vertices)
        except ValueError:
            count = 0
        for i in range(1, min(count, 4) + 1):
            verts.append({
                "x": getattr(self, f"Vertex_{i}_X"),
                "y": getattr(self, f"Vertex_{i}_Y"),
                "z": getattr(self, f"Vertex_{i}_Z")
            })
        return {
            "id": self.id,
            "name": self.Name,
            "surfaceType": self.Surface_Type,
            "constructionName": self.Construction_Name,
            "buildingSurfaceName": self.Building_Surface_Name,
            "outsideBoundaryConditionObject": self.Outside_Boundary_Condition_Object,
            "viewFactorToGround": self.View_Factor_to_Ground,
            "frameAndDividerName": self.Frame_and_Divider_Name,
            "multiplier": self.Multiplier,
            "vertices": verts
        }

class idf_ZoneVentilationDesignFlowRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Zone_Name = db.Column(db.String, nullable=False)
    Schedule_Name = db.Column(db.String, nullable=False)
    Design_Flow_Rate_Calculation_Method = db.Column(db.String, nullable=False)
    Design_Flow_Rate = db.Column(db.String, nullable=True)
    Flow_per_Zone_Floor_Area = db.Column(db.String, nullable=True)
    Flow_Rate_per_Person = db.Column(db.String, nullable=True)
    Air_Changes_per_Hour = db.Column(db.String, nullable=True)
    Ventilation_Type = db.Column(db.String, nullable=False)
    Fan_Pressure_Rise = db.Column(db.String, nullable=True)
    Fan_Total_Efficiency = db.Column(db.String, nullable=True)
    Constant_Term_Coefficient = db.Column(db.String, nullable=True)
    Temperature_Term_Coefficient = db.Column(db.String, nullable=True)
    Velocity_Term_Coefficient = db.Column(db.String, nullable=True)
    Velocity_Squared_Term_Coefficient = db.Column(db.String, nullable=True)
    Minimum_Indoor_Temperature = db.Column(db.String, nullable=True)
    Minimum_Indoor_Temp_Schedule = db.Column(db.String, nullable=True)
    Maximum_Indoor_Temperature = db.Column(db.String, nullable=True)
    Maximum_Indoor_Temp_Schedule = db.Column(db.String, nullable=True)
    Delta_Temperature = db.Column(db.String, nullable=True)
    Delta_Temp_Schedule = db.Column(db.String, nullable=True)
    Minimum_Outdoor_Temperature = db.Column(db.String, nullable=True)
    Minimum_Outdoor_Temp_Schedule = db.Column(db.String, nullable=True)
    Maximum_Outdoor_Temperature = db.Column(db.String, nullable=True)
    Maximum_Outdoor_Temp_Schedule = db.Column(db.String, nullable=True)
    Maximum_Wind_Speed = db.Column(db.String, nullable=True)

    def to_json(self):
        return {col.name.lower(): getattr(self, col.name) for col in self.__table__.columns}

class idf_Lights(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Zone_or_Space_Name = db.Column(db.String, nullable=False)
    Schedule_Name = db.Column(db.String, nullable=False)
    Design_Level_Calculation_Method = db.Column(db.String, nullable=False)
    Lighting_Level = db.Column(db.String, nullable=True)
    Watts_per_Zone_Floor_Area = db.Column(db.String, nullable=True)
    Watts_per_Person = db.Column(db.String, nullable=True)
    Return_Air_Fraction = db.Column(db.String, nullable=True)
    Fraction_Radiant = db.Column(db.String, nullable=True)
    Fraction_Visible = db.Column(db.String, nullable=True)
    Fraction_Replaceable = db.Column(db.String, nullable=True)
    End_Use_Subcategory = db.Column(db.String, nullable=True)

    def to_json(self):
        return {col.name.lower(): getattr(self, col.name) for col in self.__table__.columns}

class idf_WindowShadingControl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Zone_Name = db.Column(db.String, nullable=False)
    Shading_Control_Sequence = db.Column(db.String, nullable=False)
    Shading_Type = db.Column(db.String, nullable=False)
    Construction_with_Shading_Name = db.Column(db.String, nullable=True)
    Shading_Control_Type = db.Column(db.String, nullable=False)
    Schedule_Name = db.Column(db.String, nullable=True)
    Setpoint = db.Column(db.String, nullable=True)
    Shading_Control_Is_Scheduled = db.Column(db.String, nullable=False)
    Glare_Control_Is_Active = db.Column(db.String, nullable=False)
    Shading_Device_Material_Name = db.Column(db.String, nullable=True)
    Slat_Angle_Control_Type = db.Column(db.String, nullable=False)
    Slat_Angle_Schedule_Name = db.Column(db.String, nullable=True)
    Setpoint_2 = db.Column(db.String, nullable=True)
    Daylighting_Control_Object_Name = db.Column(db.String, nullable=True)
    Multiple_Surface_Control_Type = db.Column(db.String, nullable=False)
    # Hasta 10 superficies de enrase
    Fenestration_Surface_1_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_2_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_3_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_4_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_5_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_6_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_7_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_8_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_9_Name = db.Column(db.String, nullable=True)
    Fenestration_Surface_10_Name = db.Column(db.String, nullable=True)

    def to_json(self):
        return {col.name.lower(): getattr(self, col.name) for col in self.__table__.columns}
    
class current_ems_output_variable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String, nullable=False)
    Variable_Name = db.Column(db.String, nullable=False)
    Type_of_Data = db.Column(db.String, nullable=False)       # Averaged|Summed
    Update_Frequency = db.Column(db.String, nullable=False)   # ZoneTimestep|SystemTimestep
    EMS_Program_or_Sub = db.Column(db.String, nullable=True)  # optional
    Units = db.Column(db.String, nullable=True)               # optional

    def to_json(self):
        return {
            "id": self.id,
            "name": self.Name,
            "variableName": self.Variable_Name,
            "typeOfData": self.Type_of_Data,
            "updateFrequency": self.Update_Frequency,
            "emsProgramOrSub": self.EMS_Program_or_Sub,
            "units": self.Units
        }