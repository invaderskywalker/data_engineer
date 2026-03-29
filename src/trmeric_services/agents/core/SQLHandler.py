
class SQL_Handler:
    """
    We are working with a postgress database.
    """

    def __init__(self, baseQuery: str):
        self.baseQuery = baseQuery
        self.conditionals = []
        self.group_conditionals = []

    def handleArguments(self, conditional, value):
        if not value:
            return
        print("--debug handleArguments",value," ",conditional) 
        conditionalType = conditional["conditional"]
        if conditionalType == "in":
            self.handleInConditionals(
                conditional["name"], value, conditional["type"]
            )
        elif conditionalType == "date-bound":
            upperBound = None
            lowerBound = None
            if "upper_bound" in value:
                upperBound = value["upper_bound"]
            if "lower_bound" in value:
                lowerBound = value["lower_bound"]
            self.handleDateConditionals(conditional["name"], upperBound, lowerBound)
        elif conditionalType == "like":
            self.handleLikeConditionals(
                conditional["name"],
                value,
                conditional["type"],
                conditional.get("reverse", False),
            )
        elif conditionalType == "range":
            upperBound = None
            lowerBound = None
            if "upper_bound" in value:
                upperBound = value["upper_bound"]
            if "lower_bound" in value:
                lowerBound = value["lower_bound"]
            self.handleRangeConditions(conditional["name"], upperBound, lowerBound)

    def handleInConditionals(self, name, value, input_type):
        print("in handleInConditionals ", name, value, input_type)
        if not value:
            return
        value = f"({', '.join(map(str, value))})"
        self.conditionals.append((name, f"{name} IN {value}"))

    def handleDateConditionals(self, name, upper_bound, lower_bound):
        print("--debug handledatecondition",lower_bound," ",type(lower_bound))
        if not upper_bound and not lower_bound:
            return
        if upper_bound:
            self.conditionals.append((name, f"{name} <= '{str(upper_bound)}'"))
        if lower_bound:
            self.conditionals.append((name, f"{name} >= '{str(lower_bound)}'"))

    def handleLikeConditionals(self, name, value, input_type, reverse):
        if not value:
            return
        if input_type == "str[]":
            nested_conditionals = []
            for v in value:
                nested_conditionals.append(f"{name} LIKE '{v}'")
            self.conditionals.append((name, f"{' OR '.join(nested_conditionals)}"))
        else:
            if reverse:
                self.conditionals.append((name, f"{value} LIKE {name}"))
            else:
                self.conditionals.append((name, f"{name} LIKE {value}"))

    def handleRangeConditions(self, name, upper_bound, lower_bound):
        if upper_bound:
            self.conditionals.append((name, f"{name} <= {upper_bound}"))
        if lower_bound:
            self.conditionals.append((name, f"{name} >= {lower_bound}"))

    def generateConditionals(self):
        query = ""
        if self.conditionals:
            query = "WHERE " + " OR ".join([c[1] for c in self.conditionals])
        return query

    def createSQLQuery(self):
        query = self.baseQuery
        if self.conditionals:
            query += " WHERE " + " AND ".join([c[1] for c in self.conditionals])
        return query
