class Athlete:
    def __init__(self, *args):
        if len(args) == 7:
            self.name = args[0]
            self.gender = args[1]
            self.birthdate = args[2]
            self.swimstr = args[3]
            self.bikestr = args[4]
            self.runstr = args[5]
            self.deviceid = args[6]
        elif len(args) == 1:
            self.name=args[0]["name"]
            self.gender = args[0]["gender"]
            self.birthdate = args[0]["birthdate"]
            self.swimstr = int(args[0]["swimstr"])
            self.bikestr = int(args[0]["bikestr"])
            self.runstr = int(args[0]["runstr"])
            self.deviceid = args[0]["deviceid"]


