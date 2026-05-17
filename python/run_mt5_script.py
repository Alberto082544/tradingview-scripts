"""
Automatización completa:
1. Lanza MT5 si no está abierto con ventana visible
2. Espera a que se inicialice
3. Encuentra LoadGBPJPY_DK en el Navigator
4. Lo ejecuta con doble clic
"""
import ctypes, struct, time, sys, os, subprocess
import win32gui, win32api, win32con, win32process
import psutil

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TARGET   = "LoadGBPJPY_DK"
MT5_EXE  = r"C:\Program Files\Capital Point Trading MT5 Terminal\terminal64.exe"

TVM_GETNEXTITEM = 0x110A; TVM_GETITEMW = 0x110C; TVM_SELECTITEM = 0x110B
TVM_GETCOUNT = 0x1105;    TVM_GETITEMRECT = 0x1104
TVGN_ROOT=0; TVGN_NEXT=1; TVGN_CHILD=4; TVGN_CARET=9; TVIF_TEXT=1
k32 = ctypes.windll.kernel32; u32 = ctypes.windll.user32


def find_mt5_window():
    """Devuelve (hwnd_main, hwnd_tree) si MT5 está visible, None si no."""
    results = {}
    def cb(h, _):
        try:
            cls = win32gui.GetClassName(h)
            txt = win32gui.GetWindowText(h)
            if cls == 'MetaQuotes::MetaTrader::5.00' and txt:
                results.setdefault('wins', []).append(h)
        except Exception:
            pass
    # Buscar en los procesos terminal64.exe directamente
    for proc in psutil.process_iter(['pid', 'name']):
        if 'terminal64' in proc.info['name'].lower():
            pid = proc.info['pid']
            try:
                def enum_cb(h, l):
                    try:
                        _, p = win32process.GetWindowThreadProcessId(h)
                        if p == pid:
                            cls = win32gui.GetClassName(h)
                            txt = win32gui.GetWindowText(h)
                            if txt:
                                l.append((h, cls, txt))
                    except Exception:
                        pass
                wins = []
                win32gui.EnumChildWindows(win32gui.GetDesktopWindow(), enum_cb, wins)
                # Buscar ventana principal con titulo de MT5
                mt5_wins = [(h, c, t) for h, c, t in wins if 'MetaQuotes' in c or 'CapitalPoint' in t]
                if mt5_wins:
                    return mt5_wins[0][0], pid
            except Exception:
                pass
    return None, None


def get_tree_view(hwnd_main):
    trees = []
    def cb(h, l):
        try:
            if win32gui.GetClassName(h) == 'SysTreeView32':
                cnt = u32.SendMessageW(h, TVM_GETCOUNT, 0, 0)
                l.append((h, cnt))
        except Exception:
            pass
    win32gui.EnumChildWindows(hwnd_main, cb, trees)
    if not trees:
        return None
    trees.sort(key=lambda x: -x[1])
    return trees[0][0]


def read_tree_items(hwnd_tree):
    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(hwnd_tree, ctypes.byref(pid))
    hproc = k32.OpenProcess(0x1F0FFF, False, pid.value)
    remote   = k32.VirtualAllocEx(hproc, 0, 700, 0x3000, 0x04)
    rem_text = remote + 80
    FMT = '<IxxxxQIIQIiiiq'  # 56 bytes, 10 valores

    def get_text(hitem):
        tv = struct.pack(FMT, TVIF_TEXT,
                         hitem    & 0xFFFFFFFFFFFFFFFF,
                         0, 0,
                         rem_text & 0xFFFFFFFFFFFFFFFF,
                         255, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(tv)
        k32.WriteProcessMemory(hproc, remote, buf, len(tv), None)
        u32.SendMessageW(hwnd_tree, TVM_GETITEMW, 0, remote)
        rb = ctypes.create_string_buffer(512)
        k32.ReadProcessMemory(hproc, rem_text, rb, 512, None)
        return rb.raw.decode('utf-16-le', errors='ignore').split('\x00')[0]

    def walk(h, depth=0):
        items = []
        while h:
            txt = get_text(h)
            items.append((h, depth, txt))
            child = u32.SendMessageW(hwnd_tree, TVM_GETNEXTITEM, TVGN_CHILD, h)
            if child:
                items.extend(walk(child, depth + 1))
            h = u32.SendMessageW(hwnd_tree, TVM_GETNEXTITEM, TVGN_NEXT, h)
        return items

    root  = u32.SendMessageW(hwnd_tree, TVM_GETNEXTITEM, TVGN_ROOT, 0)
    items = walk(root)
    k32.VirtualFreeEx(hproc, remote, 0, 0x8000)
    k32.CloseHandle(hproc)
    return items


def click_item(hwnd_main, hwnd_tree, hitem):
    u32.SetForegroundWindow(hwnd_main)
    u32.ShowWindow(hwnd_main, 9)
    time.sleep(0.5)
    u32.SendMessageW(hwnd_tree, TVM_SELECTITEM, TVGN_CARET, hitem)
    time.sleep(0.3)
    rc = (ctypes.c_long * 4)(hitem, 0, 0, 0)
    u32.SendMessageW(hwnd_tree, TVM_GETITEMRECT, 1, ctypes.byref(rc))
    pt = ctypes.wintypes.POINT(rc[0], rc[1])
    u32.ClientToScreen(hwnd_tree, ctypes.byref(pt))
    cx = pt.x + 20; cy = pt.y + 6
    win32api.SetCursorPos((cx, cy))
    time.sleep(0.2)
    for _ in range(2):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.06)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.1)
    time.sleep(1.2)
    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)


# ── MAIN ───────────────────────────────────────────────────────────────────────
print("Buscando MT5...")
hwnd_main, pid = find_mt5_window()

if not hwnd_main:
    print("MT5 sin ventana. Lanzando...")
    subprocess.Popen([MT5_EXE], creationflags=subprocess.CREATE_NEW_CONSOLE)
    for _ in range(20):
        time.sleep(2)
        hwnd_main, pid = find_mt5_window()
        if hwnd_main:
            print(f"MT5 abierto: hwnd={hwnd_main}")
            time.sleep(3)  # dejar que cargue el Navigator
            break
    else:
        print("MT5 no abrió en 40 s"); sys.exit(1)
else:
    print(f"MT5 encontrado: hwnd={hwnd_main}")

hwnd_tree = get_tree_view(hwnd_main)
if not hwnd_tree:
    print("Navigator no encontrado"); sys.exit(1)
print(f"Navigator TreeView: {hwnd_tree}  ({u32.SendMessageW(hwnd_tree, TVM_GETCOUNT, 0, 0)} items)")

items = read_tree_items(hwnd_tree)
found = None
print("Árbol del Navigator:")
for h, d, txt in items:
    if txt:
        print("  " * d + repr(txt))
    if txt.strip() == TARGET:
        found = h

if not found:
    print(f"\nNO ENCONTRADO: {TARGET}")
    print("Compila y refresca el Navigator (clic derecho > Actualizar).")
    sys.exit(1)

print(f"\nEjecutando {TARGET}...")
click_item(hwnd_main, hwnd_tree, found)
print("LISTO — revisa el Journal de MT5 para confirmar.")
