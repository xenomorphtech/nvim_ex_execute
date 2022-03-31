import vim
import threading
import socket
import sys
import select
import struct

HOST = "127.0.0.1"
PORT = 7099

sock = None
read_to_buf = False
buffer = b""

def set_tobuf(val):
    global read_to_buf
    read_to_buf = val

def output_poller():
    global read_to_buf
    global sock
    global buffer
    if not sock:
        return

    output = read_output()
    buffer += output
    if len(buffer) > 4:
        (l,) = struct.unpack(">I", buffer[:4])    
        if l >= len(buffer) - 4:
            output = (buffer[4:][:l+4]).decode()
            buffer = buffer[l + 4:]
            if read_to_buf:
                vim.async_call(tappend, output)
            else:
                vim.async_call(tprint, output)
    threading.Timer(0.3, output_poller).start()


def connect(host = HOST, port = PORT, password = ""):
    """ Opens the connection """
    global sock

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect the socket to the port where the server is listening
    server_address = (host, port)
    print('connecting to %s port %s' % server_address)
    sock.connect(server_address)
    val = bytes("auth:" + password, "utf-8")
    sock.send(struct.pack(">I", len(val)) + val)
    output_poller()


def close():
    global sock
    if sock:
        sock.close()
        sock = None


def send_string(value):
    """ Sends the desired string through the connection """
    global sock
    if not sock:
        print("Not connected")
        return
    if value:
        sock.send(struct.pack(">I", len(bytes(value, 'utf-8'))))
        sock.sendall(bytes(value, 'utf-8'))


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


def send_block():
    """ Send the text determined by empty lines . """
    send_string(get_block())

def send_commented_block():
    """ Send the text determined by empty lines . """
    send_string(get_commented_block())

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


def get_block():
    lines = vim.current.buffer
    start_selection, col = vim.current.buffer.mark("{")
    # vim index is not 0 based, facepalm.jpg
    start_selection -= 1
    end_selection, col = vim.current.buffer.mark("}")

    result = join_lines(lines[start_selection:end_selection])

    return result


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
    result = get_commented_block_line_numbers(current_line, buffer_lines)
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
    for line in lines[top_placeholder+1:]:
        if line.startswith("#"):
            break
        bottom_placeholder += 1

    print(bottom_placeholder)
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
    return "\r\n".join(lines)


def read_output():
    global sock
    to_return = b""
    if not sock:
        vim.async_call(tprint, "Not connected")
        return to_return
    ready_to_read, ready_to_write, in_error = select.select([sock], [], [sock], 0)

    if in_error != []:
        sock = None
    try:
       if ready_to_read != []: 
         to_return = sock.recv(4095)
    except:
        vim.async_call(tprint, "Error reading from extempore connection")
        sock = None
    return to_return

def tprint(text):
    print(text) 

def tappend(text):
    vim.current.buffer.append(text)
