DOMAINS = {
    "MECHANICAL_TORQUE": "mechanical_torque",
    "FLUID_FUEL": "fluid_fuel",
    "COMMAND_SIGNAL": "command_signal",
    "ELECTRICAL_POWER": "electrical_power",
    "MECHANICAL_FASTENING": "mechanical_fastening",
}

TYPE_TO_DOMAIN = {
    # --- Mechanical Torque Domain ---
    "DriveIF": DOMAINS["MECHANICAL_TORQUE"],
    "AxleMountIF": DOMAINS["MECHANICAL_TORQUE"],
    "WheelHubIF": DOMAINS["MECHANICAL_TORQUE"],
    "DrivePwrPort": DOMAINS["MECHANICAL_TORQUE"],
    "GearPort": DOMAINS["MECHANICAL_TORQUE"],
    "TireInput": DOMAINS["MECHANICAL_TORQUE"],
    "TireOutput": DOMAINS["MECHANICAL_TORQUE"],
    
    # --- Mechanical Torque Domain (from VehicleModel.sysml) ---
    "ClutchPort": DOMAINS["MECHANICAL_TORQUE"],        # Connects engine to transmission
    "ShaftPort_a": DOMAINS["MECHANICAL_TORQUE"],       # Transmission shaft
    "ShaftPort_b": DOMAINS["MECHANICAL_TORQUE"],       # Driveshaft input
    "ShaftPort_c": DOMAINS["MECHANICAL_TORQUE"],       # Driveshaft output
    "ShaftPort_d": DOMAINS["MECHANICAL_TORQUE"],       # Axle shaft
    "DiffPort": DOMAINS["MECHANICAL_TORQUE"],          # Differential ports
    "AxlePort": DOMAINS["MECHANICAL_TORQUE"],          # Axle connections
    "AxleToWheelPort": DOMAINS["MECHANICAL_TORQUE"],   # Axle to wheel
    "WheelToAxlePort": DOMAINS["MECHANICAL_TORQUE"],   # Wheel to axle
    "WheelToRoadPort": DOMAINS["MECHANICAL_TORQUE"],   # Wheel to road contact
    "VehicleToRoadPort": DOMAINS["MECHANICAL_TORQUE"], # Vehicle to road
    
    # --- Fluid/Fuel Domain ---
    "FuelPort": DOMAINS["FLUID_FUEL"],
    
    # --- Command/Signal Domain ---
    "IgnitionCmdPort": DOMAINS["COMMAND_SIGNAL"],
    "PwrCmdPort": DOMAINS["COMMAND_SIGNAL"],
    "FuelCmdPort": DOMAINS["COMMAND_SIGNAL"],
    "ControlPort": DOMAINS["COMMAND_SIGNAL"],
    "CruiseControlPort": DOMAINS["COMMAND_SIGNAL"],
    "SpeedSensorPort": DOMAINS["COMMAND_SIGNAL"],
    "SetSpeedPort": DOMAINS["COMMAND_SIGNAL"],
    "StatusPort": DOMAINS["COMMAND_SIGNAL"],
    "DriverCmdPort": DOMAINS["COMMAND_SIGNAL"],
    "HandPort": DOMAINS["COMMAND_SIGNAL"],

    # --- Electrical Power Domain ---
    "BatteryInput": DOMAINS["ELECTRICAL_POWER"],
    "BatteryOutput": DOMAINS["ELECTRICAL_POWER"],
    "MotorInput": DOMAINS["ELECTRICAL_POWER"], 
    "MotorOutput": DOMAINS["ELECTRICAL_POWER"],
    
    "LugNutPort": DOMAINS["MECHANICAL_FASTENING"],
    "LugNutCompositePort": DOMAINS["MECHANICAL_FASTENING"],
    "ShankPort": DOMAINS["MECHANICAL_FASTENING"],
    "ShankCompositePort": DOMAINS["MECHANICAL_FASTENING"],
}

VALID_CONNECTIONS = {
    DOMAINS["MECHANICAL_TORQUE"]: [DOMAINS["MECHANICAL_TORQUE"]],
    DOMAINS["FLUID_FUEL"]: [DOMAINS["FLUID_FUEL"]],
    DOMAINS["COMMAND_SIGNAL"]: [DOMAINS["COMMAND_SIGNAL"]],
    DOMAINS["ELECTRICAL_POWER"]: [DOMAINS["ELECTRICAL_POWER"]],
    DOMAINS["MECHANICAL_FASTENING"]: [DOMAINS["MECHANICAL_FASTENING"]],
}

