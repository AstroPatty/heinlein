class HeinleinError(Exception):
    pass


class HeinleinConfigError(HeinleinError):
    @classmethod
    def doesnt_exist(cls, option: str) -> "HeinleinConfigError":
        return cls(f"'{option}' is not a valid configuration option")
