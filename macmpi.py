#!/usr/bin/env python3

import iterm2
import sys
import subprocess
import tempfile
import os
import glob
import time
import shutil
import pty
import atexit
import psutil
import shlex

PROGRAM_PATH = os.path.abspath(__file__)
MPI_EXEC = shlex.split(os.environ.get("MACMPI_MPIRUN", "mpiexec"))


def check_dtach():
    dtach = shutil.which("dtach")
    if dtach == None:
        raise RuntimeError("This tool requires dtach. We could not find dtach using which.")


def print_help():
    print(
        """macmpi is a tool for running MPI processes in iTerm2 tabs. Run with:

    macmpi <nproc> <executable>

If the program crashes there are likely to be dtach instances that will need
manually cleaning up. See README.rst for configuration.
"""
    )

    exit(-1)


def check_args():
    if len(sys.argv) < 3:
        print_help()


class TerminalSession:
    def __init__(self):
        self.connection = None
        self.app = None
        self.window = None

    async def connect(self):
        self.connection = await iterm2.Connection.async_create()

    async def add(self, n):
        self.app = await iterm2.async_get_app(self.connection)
        self.window = await iterm2.Window.async_create(self.connection)
        for px in range(n - 1):
            await self.window.async_create_tab()
        await self.window.tabs[0].async_activate()

    async def send_keys(self, ix, keys):
        await self.window.tabs[ix].current_session.async_send_text(keys)

    async def send_enter(self):
        for tab in self.window.tabs:
            await tab.current_session.async_send_text("\n")

    async def cleanup(self):
        try:
            await self.window.async_close()
        except Exception:
            pass


_cleanup = []


def cleanup():
    for cx in _cleanup:
        cx()


async def main(connection):
    # register the atexit function that tries to cleanup if needed
    atexit.register(cleanup)

    it2session = TerminalSession()
    await it2session.connect()

    nproc = int(sys.argv[1])
    cmd = sys.argv[2:]

    # create n windows or panes
    await it2session.add(nproc)

    # directory for dtach sockets
    temp_dir = tempfile.TemporaryDirectory(prefix="it2-mpi")

    # do the mpi launch
    launch_cmd = MPI_EXEC + ["-n", str(nproc), sys.executable, PROGRAM_PATH, "DTACH_CHILD", temp_dir.name] + cmd
    mpiproc = subprocess.Popen(launch_cmd)

    # Wait for all the dtach processes to create sockets before trying to connect to them
    def get_socket_files():
        return sorted(glob.glob(os.path.join(temp_dir.name, "*", "dtach.socket")))

    time.sleep(0.2)
    socket_files = get_socket_files()
    while len(socket_files) != nproc:
        print("Waiting for dtach sockets to appear. Found {} out of {}.".format(len(socket_files), nproc))
        time.sleep(0.2)
        socket_files = get_socket_files()
    print("Waiting for dtach sockets to appear. Found {} out of {}.".format(len(socket_files), nproc))
    mpiproc_children = psutil.Process(mpiproc.pid).children(recursive=True)

    # run the launch command in each window or pane
    for px in range(nproc):
        win_cmd = "dtach -a " + socket_files[px] + "\n"
        await it2session.send_keys(px, win_cmd)

    # loop over the iterm tabs and send a newline to allow the execution to continue
    await it2session.send_enter()

    def cleanup_mpi():
        try:
            temp_dir.cleanup()
        except Exception as e:
            print(e)

        try:
            mpiproc.kill()
        except Exception as e:
            pass

        for pidx in mpiproc_children:
            try:
                pidx.kill()
            except Exception as e:
                pass

    _cleanup.append(cleanup_mpi)

    # Try to terminate cleanly
    mpiproc.communicate()
    a = input("\nPress Enter to close iTerm window and quit")
    await it2session.cleanup()


def dtach_child():
    """
    Creates a new dtach instance with a socket in the temp dir that runs this script again to invoke exec_child.
    """
    dtach_socket = os.path.join(tempfile.mkdtemp(prefix=str(os.getpid()) + "_", dir=sys.argv[2]), "dtach.socket")
    cmd = sys.argv[3:]
    dtach_cmd = ["dtach", "-N", dtach_socket, sys.executable, PROGRAM_PATH, "EXEC_CHILD", sys.argv[2]] + cmd

    # Using execv worked for mpich/openmpi but not intel MPI, using pty.spawn seems to keep intel MPI happy
    pty.spawn(dtach_cmd)


def exec_child():
    """
    Waits for the newline from iTerm then runs the user command.
    """

    # Wait for the newline to be send that indicates all the iTerm windows are connected.
    a = input("Waiting for iTerm windows to all be connected...\n")

    # launch the actual user command
    cmd = sys.argv[3:]
    os.execv(shutil.which(cmd[0]), cmd)


if __name__ == "__main__":
    check_dtach()
    check_args()

    if sys.argv[1] == "DTACH_CHILD":
        dtach_child()
    elif sys.argv[1] == "EXEC_CHILD":
        exec_child()
    else:
        iterm2.run_until_complete(main)
