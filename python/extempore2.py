import vim
import telnetlib
import threading

HOST = "localhost"
PORT = 7099

telnet = None


def output_poller():
    global telnet
    if not telnet:
        return
    output = read_output()
    if output != "":
        print(output)
    threading.Timer(0.3, output_poller).start()


def connect():
    """ Opens the connection """
    global telnet
    telnet = telnetlib.Telnet(HOST, PORT)
    output_poller()


def close():
    global telnet
    if telnet:
        telnet.close()
        telnet = None


def send_string(value):
    """ Sends the desired string through the connection """
    global telnet
    if not telnet:
        print("Not connected")
        return
    if value:
        telnet.write(value, 'utf-8')


def get_user_input():
    vim.command('call inputsave()')
    vim.command("let user_input = input('extempore>: ')")
    vim.command('call inputrestore()')
    user_input = vim.eval('user_input')
    return user_input


def echo_user_input():
    print(get_user_input())


def send_user_input():
    send_string(get_user_input()+"\r\n")


def panic():
    send_string("(bind-func dsp (lambda (in:SAMPLE time:i64 channel:SAMPLE data:SAMPLE*) 0.0))\r\n")


def send_enclosing_block():
    """ Grab the enclosing function block and send it, ie if you
        are inside a (define ...) somewhere, we want to send that."""
    send_string(get_enclosing_block())


def send_entire_file():
    send_string(get_entire_file())


def send_selection():
    """ Send the text determined by the '<' and '>' marks. """
    send_string(get_selection())


def send_bracket_selection():
    """ Send the text determined by the '[' and ']' marks. """
    send_string(get_bracket_selection())


def get_entire_file():
    lines = vim.current.buffer
    result = join_lines(lines)
    return result


def send_path_file(path):
    file_data = open(path).read()
    send_string(file_data+"\r\n")


def get_selection():
    lines = vim.current.buffer
    start_selection, col = vim.current.buffer.mark("<")
    # vim index is not 0 based, facepalm.jpg
    start_selection -= 1
    end_selection, col = vim.current.buffer.mark(">")

    result = join_lines(lines[start_selection:end_selection])

    return result


def get_bracket_selection():
    lines = vim.current.buffer
    start_selection, col = vim.current.buffer.mark("[")
    # vim index is not 0 based, facepalm.jpg
    start_selection -= 1
    end_selection, col = vim.current.buffer.mark("]")

    result = join_lines(lines[start_selection:end_selection])

    return result

def get_commented_block():
    current_line, current_col = vim.current.window.cursor
    # facepalm.jpg, really vim?
    current_line -= 1
    buffer_lines = vim.current.buffer
    result = get_enclosing_block_line_numbers(current_line, buffer_lines)
    if result is None:
        return None
    start_line, end_line = result

    result = join_lines(vim.current.buffer[start_line:end_line+1])
    return result


def get_commented_block_line_numbers(line_num, lines):
    top_placeholder = line_num
    # lines from current to beginning, reversed
    for line in lines[:line_num+1][::-1]:
        if line.startswith("#"):
            break
        top_placeholder -= 1

    bottom_placeholder = top_placeholder
    # lines from top_placeholder to end
    for line in lines[top_placeholder:]:
        if line.startswith("#"):
            break
        bottom_placeholder += 1

    # if entire code block is above the current line, return None
    if bottom_placeholder < line_num:
        return None
    else:
        return (top_placeholder, bottom_placeholder)


def get_enclosing_block():
    current_line, current_col = vim.current.window.cursor
    # facepalm.jpg, really vim?
    current_line -= 1
    buffer_lines = vim.current.buffer
    result = get_enclosing_block_line_numbers(current_line, buffer_lines)
    if result is None:
        return None
    start_line, end_line = result

    result = join_lines(vim.current.buffer[start_line:end_line+1])
    return result


 
def get_enclosing_block_line_numbers(line_num, lines):
    """ Given the current line number, and a list of lines representing
        the buffer, return the line indexes of the beginning and end of
        the current block.

        Steps:
            1. Go through previous lines, find one which matches '^(', ie
            :xa


                start of line is a paren. Call this line top_placeholder.
            2. From top_placeholder, go towards bottom of file until left and
                right parent counts are equal. Call this line
                bottom_placeholder
            3. Return the tuple (top, bottom) placeholders as long as the
                current line resides in them. Else, return None.
            """
    top_placeholder = line_num
    # lines from current to beginning, reversed
    for line in lines[:line_num+1][::-1]:
        if line.startswith("("):
            break
        top_placeholder -= 1

    left_parens = 0
    right_parens = 0
    bottom_placeholder = top_placeholder
    # lines from top_placeholder to end
    for line in lines[top_placeholder:]:
        left_parens += line.count("(")
        right_parens += line.count(")")
        if left_parens == right_parens:
            break
        bottom_placeholder += 1

    # if entire code block is above the current line, return None
    if bottom_placeholder < line_num:
        return None
    else:
        return (top_placeholder, bottom_placeholder)


def join_lines(lines):
    """ Join lines by spaces, remove any comments, and end with newline"""
    result = ""
    for line in lines:
        # remove comment; TODO: do less hacky
        result += line.split(";")[0]

    result += "\r\n"
    return result


def read_output():
    global telnet
    to_return = ""
    if not telnet:
        print("Not connected")
        return to_return
    try:
        to_return = telnet.read_eager()
    except:
        print("Error reading from extempore connection")
        telnet = None
    return to_return
