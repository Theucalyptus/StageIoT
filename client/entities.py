
SIMILARITY_COEF=0.7

class Entity:

    def __init__(self):
        self.pos1=0
        self.pos2=0
        self.label="no_label_entity"

    def __init__(self, label, pos1, pos2):
        self.pos1 = pos1
        self.pos2 = pos2
        self.label = label

    def __str__(self):
        return self.label + "," + str(self.pos1) + "," + str(self.pos2)

    def setLabel(self, newLabel):
        self.label = newLabel

    def setCoord(self, pos1, pos2):
        self.pos1 = pos1
        self.pos2 = pos2

    def getCoords(self):
        return (self.pos1, self.pos2)


class Object(Entity):

    def __init__(self, label, pos1, pos2, pos3, size1, size2):
        super().__init__(label, pos1, pos2)
        self.sizeX = size1
        self.sizeY = size2

    def overlap(self, obj):
        """
            Return true if two object overlap
        """
        x1 = self.pos1 - self.sizeX/2
        y1 = self.pos2 - self.sizeY/2 
        x2 = obj.pos1 - obj.sizeX/2 
        y2 = obj.pos2 - obj.sizeY/2

        clampX = max(x1, x2)
        clampY = max(y1, y2)

        overlap_surface = clampX*clampY
        ratio = 2 * overlap_surface / (x1*y1 + x2*y2)
        print(ratio)
        return ratio > SIMILARITY_COEF

class Device(Entity):

    def __init__(self):
        super().__init__("device", 0, 0)


class ObjectSet():

    def __init__(self):
        self.objects = []

    def addNew(self, newObj):
        """
            Adds a new object to the set if not already present.
            Compares the new object with all object in the set using the Object.overlap method
            Update the object is already in the set
            Returns True if the object has been added, false if it was already in the set
        """
        matching=None
        for obj in self.objects:
            if obj.overlap(newObj):
                matching=obj
                break
        if matching:
            self.objects.remove(matching)
        
        self.objects.append(newObj)
        return (matching == None)

    def __str__(self):
        output = ""
        for obj in self.objects:
            output+= str(obj) + ";"
        return output
    
    def printShort(self):
        msg = ""
        for obj in self.objects:
            msg+=obj.label + "; "
        print(msg)