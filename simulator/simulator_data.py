import random

class SimulatedLiveData:
    def get_data(self):
        return {
            "RPM": f"{random.randint(600, 4000)} rpm",
            "Vehicle Speed": f"{random.randint(0, 120)} km/h",
            "Coolant Temp": f"{random.randint(70, 110)} °C",
            "Throttle Position": f"{random.randint(0, 100)} %",
            "Intake Temp": f"{random.randint(10, 60)} °C",
            "MAF Rate": f"{round(random.uniform(2.0, 25.0), 2)} g/s",
            "Fuel Pressure": f"{random.randint(250, 450)} kPa",
            "O2 Sensor (Bank 1)": f"{round(random.uniform(0.1, 0.9), 2)} V"
        }
