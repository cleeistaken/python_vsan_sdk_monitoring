from colored import fg, attr


def convert_bytes(nb_bytes: int) -> str:
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while nb_bytes >= 1024 and i < len(suffixes) - 1:
        nb_bytes /= 1024.
        i += 1
    f = ('%.2f' % nb_bytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])


def print_green(string: str) -> str:
    return '%s%s%s' % (fg('green'), string, attr('reset'))


def print_yellow(string: str) -> str:
    return '%s%s%s' % (fg('yellow'), string, attr('reset'))


def print_red(string) -> str:
    return '%s%s%s' % (fg('red'), string, attr('reset'))


def print_yes_no(value: bool) -> str:
    if value is None:
        return print_yellow('Unknown')
    return print_green('Yes') if value else print_red('No')


def print_no_yes(value: bool) -> str:
    if value is None:
        return print_yellow('Unknown')
    return print_red('Yes') if value else print_green('No')


def print_thresholds_inc(value: float, yellow: int = 60, red: int = 80):
    if value < yellow:
        return '%s%.2f%%%s' % (fg('green'), value, attr('reset'))
    elif value < red:
        return '%s%.2f%%%s' % (fg('yellow'), value, attr('reset'))
    else:
        return '%s%.2f%%%s' % (fg('red'), value, attr('reset'))


def print_thresholds_dec(value: float, green: int = 40, yellow: int = 20):
    if value > green:
        return '%s%.2f%%%s' % (fg('green'), value, attr('reset'))
    elif value > yellow:
        return '%s%.2f%%%s' % (fg('yellow'), value, attr('reset'))
    else:
        return '%s%.2f%%%s' % (fg('red'), value, attr('reset'))

