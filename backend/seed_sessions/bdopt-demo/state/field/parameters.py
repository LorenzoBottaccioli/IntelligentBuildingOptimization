import numpy as np

parameter = {}
# fmi_gym parameter
parameter['seed'] = 1
parameter['store_data'] = True

# fmu parameter
dtype = np.float64
parameter['fmu_step_size'] = 600  # s, = 3600 / 6 timesteps per hour of the model
parameter['fmu_path'] = 'test.fmu'
parameter['fmu_start_time'] = 0 * 60 * 60 * 24  # day 0, 1 Jan 00:00
parameter['fmu_warmup_time'] = None  # no fmi_gym warm-up: the controller acts from the start
parameter['fmu_final_time'] = 365 * 60 * 60 * 24  # day 365, 1 Jan 00:00

# data exchange parameter
parameter['action_names'] = ["ZONEWEST_Heating_Setpoint_FMU","ZONESOUTH_Heating_Setpoint_FMU","ZONEEAST_Heating_Setpoint_FMU","ZONENORTH_Heating_Setpoint_FMU"]
parameter['action_min'] = np.array([10,10,10,10], dtype=np.float64)
parameter['action_max'] = np.array([30,30,30,30], dtype=np.float64)
parameter['observation_names'] = ["DistrictHeating_Facility","Electricity_Facility","Zone_Air_Temperature_ZONEWEST","Zone_Air_Temperature_ZONESOUTH","Zone_Air_Temperature_ZONEEAST","Zone_Air_Temperature_ZONENORTH","Site_Outdoor_Air_Drybulb_Temperature_Environment","Site_Outdoor_Air_Relative_Humidity_Environment","Site_Wind_Speed_Environment","Site_Direct_Solar_Radiation_Rate_per_Area_Environment"]
parameter['reward_names'] = []