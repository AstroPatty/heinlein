
def warning_prompt(warning: str, options: list) -> str:
    print(warning)
    keys = [l[0].upper() for l in options]
    while True:
        for index, option in enumerate(options):
            print(f"{option} ({keys[index]})")
        i = input("?: ")
        if i.upper() in keys:
            return i.upper()
        else:
            print("Invalid option")


def warning_prompt_tf(warning: str) -> bool:
    options = ["Yes", "No"]
    if warning_prompt(warning, options) == "Y":
        return True
    return False