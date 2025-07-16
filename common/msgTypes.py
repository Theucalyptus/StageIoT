
class MessageTypes:
    DEVICE_UPDATE = 1 # Device update message (containing the latest data from its sensors)
    OBJECT_REPORT = 2 # Object report (list of all detected and tracked objects, their positions...)
    NEARBY_REQUEST = 3 # Request information about surroudings