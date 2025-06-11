class Device:

    def __init__(self):
        self.latitude = 0
        self.longitude = 0

    def __str__(self):
        return str(self.latitude) + str(self.longitude)