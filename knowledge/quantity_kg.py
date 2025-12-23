"""
This defines the relationships between quantity kinds and their valid units
for generating domain-aware attribute/unit errors.
"""

QUANTITY_KINDS = {
    "MASS": "mass",
    "LENGTH": "length",
    "TIME": "time",
    "SPEED": "speed",
    "ACCELERATION": "acceleration",
    "FORCE": "force",
    "TORQUE": "torque",
    "POWER": "power",
    "VOLUME": "volume",
    "TEMPERATURE": "temperature",
    "ANGLE": "angle",
    "ELECTRIC_CURRENT": "electric_current",
    "ELECTRIC_POTENTIAL": "electric_potential",
    "RESISTANCE": "resistance",
}

ISQ_TO_QUANTITY_KIND = {
    "ISQ::mass": QUANTITY_KINDS["MASS"],
    "ISQ::length": QUANTITY_KINDS["LENGTH"],
    "ISQ::time": QUANTITY_KINDS["TIME"],
    "ISQ::speed": QUANTITY_KINDS["SPEED"],
    "ISQ::acceleration": QUANTITY_KINDS["ACCELERATION"],
    "ISQ::force": QUANTITY_KINDS["FORCE"],
    "ISQ::torque": QUANTITY_KINDS["TORQUE"],
    "ISQ::power": QUANTITY_KINDS["POWER"],
    "ISQ::volume": QUANTITY_KINDS["VOLUME"],
    "ISQ::temperature": QUANTITY_KINDS["TEMPERATURE"],
    "ISQ::angularMeasure": QUANTITY_KINDS["ANGLE"],
    "ISQ::electricCurrent": QUANTITY_KINDS["ELECTRIC_CURRENT"],
    "ISQ::electricPotential": QUANTITY_KINDS["ELECTRIC_POTENTIAL"],
    "ISQ::resistance": QUANTITY_KINDS["RESISTANCE"],
    "ISQ::voltage": QUANTITY_KINDS["ELECTRIC_POTENTIAL"],  
    "ISQ::energy": "energy",  
    "ISQ::pressure": "pressure",  
    "ISQ::area": "area",  
    "ISQ::density": "density",  
    "ISQ::frequency": "frequency",  
}

VALUE_TYPE_TO_QUANTITY_KIND = {
    "MassValue": QUANTITY_KINDS["MASS"],
    "LengthValue": QUANTITY_KINDS["LENGTH"],
    "TimeValue": QUANTITY_KINDS["TIME"],
    "SpeedValue": QUANTITY_KINDS["SPEED"],
    "AccelerationValue": QUANTITY_KINDS["ACCELERATION"],
    "ForceValue": QUANTITY_KINDS["FORCE"],
    "TorqueValue": QUANTITY_KINDS["TORQUE"],
    "PowerValue": QUANTITY_KINDS["POWER"],
    "VolumeValue": QUANTITY_KINDS["VOLUME"],
    "TemperatureValue": QUANTITY_KINDS["TEMPERATURE"],
}

UNIT_TO_QUANTITY_KIND = {
    # Mass units
    "kg": QUANTITY_KINDS["MASS"],
    "g": QUANTITY_KINDS["MASS"],
    "lb": QUANTITY_KINDS["MASS"],
    "mg": QUANTITY_KINDS["MASS"],
    
    # Length units
    "m": QUANTITY_KINDS["LENGTH"],
    "cm": QUANTITY_KINDS["LENGTH"],
    "mm": QUANTITY_KINDS["LENGTH"],
    "km": QUANTITY_KINDS["LENGTH"],
    "in": QUANTITY_KINDS["LENGTH"],
    "'in'": QUANTITY_KINDS["LENGTH"],
    "ft": QUANTITY_KINDS["LENGTH"],
    "mi": QUANTITY_KINDS["LENGTH"],
    "'mi'": QUANTITY_KINDS["LENGTH"],
    
    # Time units
    "s": QUANTITY_KINDS["TIME"],
    "min": QUANTITY_KINDS["TIME"],
    "h": QUANTITY_KINDS["TIME"],
    
    # Speed units
    "m/s": QUANTITY_KINDS["SPEED"],
    "km/h": QUANTITY_KINDS["SPEED"],
    "mph": QUANTITY_KINDS["SPEED"],
    
    # Force units
    "N": QUANTITY_KINDS["FORCE"],
    
    # Power units
    "W": QUANTITY_KINDS["POWER"],
    "kW": QUANTITY_KINDS["POWER"],
    "hp": QUANTITY_KINDS["POWER"],
    
    # Volume units
    "L": QUANTITY_KINDS["VOLUME"],
    "gallon": QUANTITY_KINDS["VOLUME"],
    
    # Temperature units
    "K": QUANTITY_KINDS["TEMPERATURE"],
    "°C": QUANTITY_KINDS["TEMPERATURE"],
    "°F": QUANTITY_KINDS["TEMPERATURE"],
    
    # Angle units
    "rad": QUANTITY_KINDS["ANGLE"],
    "deg": QUANTITY_KINDS["ANGLE"],
    
    # Electrical units
    "A": QUANTITY_KINDS["ELECTRIC_CURRENT"],
    "V": QUANTITY_KINDS["ELECTRIC_POTENTIAL"],
    "Ω": QUANTITY_KINDS["RESISTANCE"],
    "'Ω'": QUANTITY_KINDS["RESISTANCE"],
}

INCOMPATIBLE_UNITS = {
    QUANTITY_KINDS["MASS"]: ["m", "s", "W", "V"],  # length, time, power, voltage
    QUANTITY_KINDS["LENGTH"]: ["kg", "s", "A", "W"],  # mass, time, current, power
    QUANTITY_KINDS["TIME"]: ["kg", "m", "V", "N"],  # mass, length, voltage, force
    QUANTITY_KINDS["SPEED"]: ["kg", "s", "W"],  # mass, time, power
    QUANTITY_KINDS["ACCELERATION"]: ["kg", "s", "V"],
    QUANTITY_KINDS["FORCE"]: ["kg", "m", "s"],
    QUANTITY_KINDS["TORQUE"]: ["kg", "m", "s"],
    QUANTITY_KINDS["POWER"]: ["kg", "m", "s"],
    QUANTITY_KINDS["VOLUME"]: ["kg", "m", "s"],
    QUANTITY_KINDS["TEMPERATURE"]: ["kg", "m", "s"],
    QUANTITY_KINDS["ANGLE"]: ["kg", "m", "s"],
    QUANTITY_KINDS["ELECTRIC_CURRENT"]: ["kg", "m", "s"],
    QUANTITY_KINDS["ELECTRIC_POTENTIAL"]: ["kg", "m", "s"],
    QUANTITY_KINDS["RESISTANCE"]: ["kg", "m", "s"],
}


ALTERNATIVE_ISQ_TYPES = {
    # Mechanical quantities - swap within mechanics domain
    "ISQ::mass": ["ISQ::force", "ISQ::density", "ISQ::pressure"],
    "ISQ::length": ["ISQ::area", "ISQ::volume", "ISQ::time"],
    "ISQ::time": ["ISQ::frequency", "ISQ::length", "ISQ::mass"],
    "ISQ::speed": ["ISQ::acceleration", "ISQ::frequency", "ISQ::force"],
    "ISQ::acceleration": ["ISQ::speed", "ISQ::force", "ISQ::pressure"],
    "ISQ::force": ["ISQ::torque", "ISQ::pressure", "ISQ::mass"],
    "ISQ::torque": ["ISQ::force", "ISQ::energy", "ISQ::power"],
    "ISQ::power": ["ISQ::energy", "ISQ::force", "ISQ::torque"],
    "ISQ::energy": ["ISQ::power", "ISQ::torque", "ISQ::force"],
    
    # Geometric quantities - swap within geometry domain
    "ISQ::volume": ["ISQ::area", "ISQ::length", "ISQ::mass"],
    "ISQ::area": ["ISQ::volume", "ISQ::length", "ISQ::density"],
    "ISQ::density": ["ISQ::mass", "ISQ::pressure", "ISQ::volume"],
    "ISQ::pressure": ["ISQ::force", "ISQ::density", "ISQ::energy"],
    
    # Angular/frequency - related to rotation/oscillation
    "ISQ::angularMeasure": ["ISQ::length", "ISQ::frequency", "ISQ::time"],
    "ISQ::frequency": ["ISQ::speed", "ISQ::angularMeasure", "ISQ::time"],
    
    # Thermal
    "ISQ::temperature": ["ISQ::energy", "ISQ::power", "ISQ::pressure"],
    
    # Electrical quantities - swap within electrical domain
    "ISQ::electricCurrent": ["ISQ::voltage", "ISQ::resistance", "ISQ::power"],
    "ISQ::electricPotential": ["ISQ::electricCurrent", "ISQ::resistance", "ISQ::energy"],
    "ISQ::voltage": ["ISQ::electricCurrent", "ISQ::resistance", "ISQ::power"],
    "ISQ::resistance": ["ISQ::voltage", "ISQ::electricCurrent", "ISQ::power"],
}