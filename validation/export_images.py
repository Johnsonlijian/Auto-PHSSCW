# -*- coding: utf-8 -*-
"""
export_images_auto.py
=====================
Integrated image export script for batch processing: Buckling + Riks analysis

Research-grade (paper-friendly) automatic image export script

Priority 1 (Standard for papers):
- Riks: Export peak LPF frame by default (optionally also export last frame)
- Legend: Always export with legend only (English display)

Priority 2 (Recommended):
- Buckling: Also export U1 (out-of-plane displacement, X = section width direction)
- Riks: Also export U1 (for comparison with buckling modes)

Usage:
1. Batch mode (auto-discover all cases):
   abaqus viewer script=export_images_auto.py

2. Single case mode (command line arguments):
   abaqus viewer script=export_images_auto.py -- <buckle_odb> <riks_odb> <output_dir> [n_modes]

Output (per model/case folder):
- Buckling
  - buckling_{view}_modeNN.png (with legend)
  - buckling_U1_{view}_modeNN.png (if EXPORT_BUCKLING_U1=True)

- Riks (default peakLPF frame)
  - riks_stress_mises_peakLPF_{view}.png (with legend)
  - riks_peeq_peakLPF_{view}.png (with legend)
  - riks_U1_peakLPF_{view}.png (if EXPORT_RIKS_U1=True)

Coordinate and view conventions:
- Member axis: Z
- Section width: X
- Section height (splice direction): Y
- Web plane: YZ (normal +X)
Three views:
- WebFront: Front view of web (+X looking at YZ)
- Side: Side view (+Y looking at XZ)
- Iso: Isometric view
"""
from abaqus import *
from abaqusConstants import *
import os
import sys
import time
import shutil

# -----------------------------
# === Research toggles (defaults implement Priority 1+2) ===
# -----------------------------
# Legend: Always export with legend only (English only, no Chinese)
EXPORT_WITH_LEGEND = True

# Riks: Export peakLPF frame by default; optionally also export last frame
EXPORT_RIKS_LAST_TOO = False

# Buckling: Also export U1 (out-of-plane displacement)
EXPORT_BUCKLING_U1 = True

# Riks: Also export U1
EXPORT_RIKS_U1 = True

# Riks: Frame strategy ('peakLPF' or 'last')
RIKS_FRAME_POLICY = 'peakLPF'

# Engineering peak LPF detection parameters
LPF_DROP_RATIO = 0.8  # Load drop threshold (0.8 = 20% drop, 0.85 = 15% drop, 0.75 = 25% drop)
LPF_DROP_PERSIST_N = 3  # Number of consecutive points below threshold for sustained drop (anti-noise, recommend 3-5)
LPF_MIN_PEAK_FRAC = 0.6  # Peak must be at least 60% of global peak to avoid early small fluctuations (0.6-0.8)
LPF_SMOOTH_WINDOW = 3  # Light smoothing window (1 = no smoothing, recommend 3 or 5)

# -----------------------------
# Timing parameters (GUI mode needs longer wait times to ensure rendering completes)
# -----------------------------
WAIT_AFTER_OPEN_SEC   = 3.0   # GUI mode: ODB opening and viewport initialization need longer time
WAIT_AFTER_SETFRAME   = 0.5   # GUI mode: Frame switching rendering needs time
WAIT_AFTER_SETVIEW    = 0.3   # GUI mode: View switching rendering needs time
WAIT_AFTER_SETVAR     = 0.5   # GUI mode: Variable setting and rendering needs time
WAIT_AFTER_PRINT_SEC  = 2.0   # GUI mode: PNG writing needs longer time (especially NAS, increased to 2 sec)
WAIT_BEFORE_CLOSE_SEC = 2.0   # GUI mode: Wait longer before closing to ensure all operations complete
PRINT_TIMEOUT_SEC     = 60.0  # GUI/NAS: PNG file appearance wait time (increased to 60 sec, NAS writes slowly)

# Long path/NAS slow write: Output to short path first, then copy back to target directory
MAX_TARGET_PATH_LEN = 200
SHORT_EXPORT_DIRNAME = "_png_tmp"

# PNG resolution (if Abaqus supports pngOptions)
PNG_W, PNG_H = 1920, 1080

# -----------------------------
# Resolve working directories
# -----------------------------
try:
    import inspect
    script_path = inspect.getfile(inspect.currentframe())
    WORK_DIR = os.path.dirname(os.path.abspath(script_path))
except:
    WORK_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()

if not WORK_DIR or not os.path.exists(WORK_DIR):
    WORK_DIR = os.getcwd()
os.chdir(WORK_DIR)

OUTPUT_DIR = os.path.join(WORK_DIR, "output")
TEMP_DIR   = os.path.join(WORK_DIR, "temp_process")
SHORT_DIR  = os.path.join(WORK_DIR, SHORT_EXPORT_DIRNAME)

def _ensure_dir(d):
    try:
        if d and (not os.path.exists(d)):
            os.makedirs(d)
    except:
        pass

_ensure_dir(SHORT_DIR)

# -----------------------------
# View / viewport helpers
# -----------------------------
def setup_export_viewport():
    """Reuse the default viewport when possible (more stable in noGUI)."""
    if 'Viewport: 1' in session.viewports.keys():
        vp = session.viewports['Viewport: 1']
    else:
        vp = session.Viewport(name='Viewport: 1', origin=(0, 0), width=597, height=336)

    try:
        vp.makeCurrent()
    except:
        pass

    # noGUI viewport size limits: 30..597, 30..336
    try:
        vp.setValues(width=597, height=336)
    except:
        pass

    # Optional: disable decorations for cleaner export
    try:
        vp.viewportAnnotationOptions.setValues(annotations=OFF, legendBox=OFF, title=OFF, compass=OFF)
    except:
        pass

    return vp

def set_legend(vp, show):
    """Set legend visibility."""
    try:
        vp.viewportAnnotationOptions.setValues(legendBox=ON if show else OFF)
    except:
        pass

def apply_view(vp, view_name):
    """Apply a predefined view using Abaqus's view rotation methods."""
    try:
        # Reset to standard view first
        vp.view.setValues(nearPlane=10, farPlane=1000, width=500, height=500,
                          cameraPosition=(0, 0, 1000), cameraTarget=(0, 0, 0),
                          cameraUpVector=(0, 1, 0))
    except:
        pass
    
    try:
        if view_name == 'WebFront':
            # Front view: X direction looking at YZ plane
            vp.view.setViewpoint(viewVector=(1, 0, 0), cameraUpVector=(0, 0, 1))
        elif view_name == 'Side':
            # Side view: Y direction looking at XZ plane  
            vp.view.setViewpoint(viewVector=(0, 1, 0), cameraUpVector=(0, 0, 1))
        elif view_name == 'Iso':
            # Isometric view
            vp.view.setViewpoint(viewVector=(1, 1, 1), cameraUpVector=(0, 0, 1))
        else:
            return False
        
        time.sleep(WAIT_AFTER_SETVIEW)
        vp.view.fitView()  # Auto-scale to fit
        time.sleep(0.2)
        return True
    except Exception as e:
        print("[apply_view] setViewpoint failed for %s: %s" % (view_name, str(e)))
        # Fallback method: use rotate
        try:
            vp.view.setValues(session.views['Iso'])
            if view_name == 'WebFront':
                vp.view.rotate(xAngle=0, yAngle=90, zAngle=0, mode=TOTAL)
            elif view_name == 'Side':
                vp.view.rotate(xAngle=90, yAngle=0, zAngle=0, mode=TOTAL)
            # Iso keeps default
            time.sleep(WAIT_AFTER_SETVIEW)
            vp.view.fitView()
            return True
        except Exception as e2:
            print("[apply_view] rotate fallback also failed: %s" % str(e2))
            return False

def get_step_with_most_frames(odb_access):
    """Find step with most frames."""
    best_step = None
    max_frames = 0
    for step_name in odb_access.steps.keys():
        n_frames = len(odb_access.steps[step_name].frames)
        if n_frames > max_frames:
            max_frames = n_frames
            best_step = step_name
    return best_step or list(odb_access.steps.keys())[0]

def _safe_target_path(path):
    final_path = os.path.abspath(path)
    if len(final_path) <= MAX_TARGET_PATH_LEN:
        return final_path, final_path, False
    base = os.path.basename(final_path)
    export_path = os.path.join(SHORT_DIR, base)
    return export_path, final_path, True

def _wait_file(path, timeout_sec=PRINT_TIMEOUT_SEC):
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return True
        except:
            pass
        time.sleep(0.1)
    return False

def print_png(vp, target_png_path):
    export_path, final_path, need_copy = _safe_target_path(target_png_path)
    _ensure_dir(os.path.dirname(final_path))
    
    # Ensure directory exists (Python 2.7 compatible)
    try:
        export_dir = os.path.dirname(export_path)
        if export_dir and not os.path.exists(export_dir):
            os.makedirs(export_dir)
        if need_copy:
            final_dir = os.path.dirname(final_path)
            if final_dir and not os.path.exists(final_dir):
                os.makedirs(final_dir)
    except Exception as e:
        print("[print_png] Failed to create directory: %s" % str(e))
        return False

    print("[print_png] Exporting to: %s" % export_path)
    try:
        session.printToFile(fileName=export_path, format=PNG, canvasObjects=(vp,))
        print("[print_png] printToFile called successfully")
    except Exception as e:
        print("[print_png] printToFile failed: %s" % str(e))
        import traceback
        traceback.print_exc()
        return False

    # GUI mode: needs longer wait time
    time.sleep(WAIT_AFTER_PRINT_SEC)
    
    # Verify file was successfully written (check actual path used first)
    check_path = export_path if need_copy else final_path
    if not _wait_file(check_path, timeout_sec=PRINT_TIMEOUT_SEC):
        print("[print_png] PNG not created or empty after timeout: %s" % check_path)
        # Wait once more and retry
        time.sleep(WAIT_AFTER_PRINT_SEC)
        if not _wait_file(check_path, timeout_sec=10):
            print("[print_png] PNG still not available: %s" % check_path)
            return False
    
    print("[print_png] PNG file confirmed: %s (size: %d bytes)" % 
          (check_path, os.path.getsize(check_path) if os.path.exists(check_path) else 0))

    if need_copy:
        try:
            shutil.copy2(export_path, final_path)
            print("[print_png] Copied to final path: %s" % final_path)
            # Verify final file
            if not _wait_file(final_path, timeout_sec=5):
                print("[print_png] WARNING: Final file not verified after copy")
        except Exception as e:
            print("[print_png] Copy back failed: %s" % str(e))
            return False

    return True

def _export_with_legend(vp, filename_base):
    """Export one png with legend only (English display)."""
    set_legend(vp, True)
    out_path = filename_base + ".png"
    return print_png(vp, out_path)

# -----------------------------
# Peak LPF frame finder (Priority 1)
# -----------------------------
def find_peak_lpf_frame_index(odb_access, step_name,
                              drop_ratio=LPF_DROP_RATIO,
                              persist_n=LPF_DROP_PERSIST_N,
                              min_peak_frac=LPF_MIN_PEAK_FRAC,
                              smooth_win=LPF_SMOOTH_WINDOW):
    """
    Engineering peak LPF (improved version: first significant peak before drop):
      Find the first local peak after which LPF drops below (drop_ratio * peak)
      for >= persist_n consecutive points. If none, fallback to global max.
      
      Improvements:
      - Use local peak detection (instead of running max)
      - Peak must be >= min_peak_frac * global_peak (avoid early small fluctuations)
      - Select earliest peak that satisfies "sustained drop after" condition
    
    Return (frame_index, peak_lpf_original, peak_time, peak_type)
      peak_type: 'peak_before_drop' or 'global_max'
    """
    step = odb_access.steps[step_name]
    last_frame = len(step.frames) - 1
    if last_frame < 0:
        return (-1, None, None, None)

    # ---- find LPF history (longest one) ----
    best_data = None
    for rname, region in step.historyRegions.items():
        try:
            if 'LPF' in region.historyOutputs.keys():
                data = region.historyOutputs['LPF'].data
                if data and (best_data is None or len(data) > len(best_data)):
                    best_data = data
        except:
            pass
    if not best_data:
        return (last_frame, None, None, None)

    # ---- build arrays ----
    t = [tv[0] for tv in best_data]
    y = [tv[1] for tv in best_data]

    # Main sign: Compression may be negative, use larger magnitude side as positive
    y_max = max(y)
    y_min = min(y)
    sign_ref = 1.0 if (y_max >= abs(y_min)) else -1.0
    y_eff = [sign_ref * v for v in y]  # For finding peaks/drops (ensure main direction is positive)

    # ---- optional smoothing (very light) ----
    if smooth_win and smooth_win > 1 and len(y_eff) >= smooth_win:
        half = smooth_win // 2
        y_sm = []
        for i in range(len(y_eff)):
            a = max(0, i - half)
            b = min(len(y_eff), i + half + 1)
            y_sm.append(sum(y_eff[a:b]) / float(b - a))
        y_use = y_sm
    else:
        y_use = y_eff

    # ---- compute global peak (for threshold) ----
    global_peak = max(y_use) if y_use else 0.0
    if global_peak <= 1e-6:
        return (last_frame, None, None, None)
    
    min_peak_val = min_peak_frac * global_peak

    # ---- find local peaks (improved: use local peaks instead of running max) ----
    # Local peak: y[i] >= y[i-1] and y[i] >= y[i+1]
    local_peaks = []
    for i in range(1, len(y_use) - 1):
        if y_use[i] >= y_use[i-1] and y_use[i] >= y_use[i+1]:
            if y_use[i] >= min_peak_val:  # Must reach minimum peak threshold
                local_peaks.append(i)
    
    # If no local peaks, fallback to global max
    if not local_peaks:
        chosen_i = max(range(len(y_use)), key=lambda k: y_use[k])
        peak_time = t[chosen_i]
        peak_lpf_original = y[chosen_i]
        frames = step.frames
        best_i = last_frame
        best_err = 1e100
        for i, fr in enumerate(frames):
            try:
                err = abs(fr.frameValue - peak_time)
                if err < best_err:
                    best_err = err
                    best_i = i
            except:
                pass
        return (best_i, peak_lpf_original, peak_time, 'global_max')

    # ---- helper: check sustained drop after a peak ----
    def has_sustained_drop_after_peak(i_peak):
        peak_val = y_use[i_peak]
        threshold = drop_ratio * peak_val
        consecutive_below = 0
        
        for j in range(i_peak + 1, len(y_use)):
            if y_use[j] <= threshold:
                consecutive_below += 1
                if consecutive_below >= persist_n:
                    return True  # Found sustained drop
            else:
                consecutive_below = 0  # Reset counter
        
        return False

    # ---- choose earliest peak with sustained drop ----
    chosen_i = None
    peak_type = 'global_max'
    
    for i_peak in local_peaks:
        if has_sustained_drop_after_peak(i_peak):
            chosen_i = i_peak
            peak_type = 'peak_before_drop'
            break
    
    # ---- fallback: global max ----
    if chosen_i is None:
        chosen_i = max(range(len(y_use)), key=lambda k: y_use[k])
        peak_type = 'global_max'

    peak_time = t[chosen_i]
    peak_lpf_original = y[chosen_i]  # Keep original sign for more intuitive output

    # ---- map time -> nearest frame ----
    frames = step.frames
    best_i = last_frame
    best_err = 1e100
    for i, fr in enumerate(frames):
        try:
            err = abs(fr.frameValue - peak_time)
            if err < best_err:
                best_err = err
                best_i = i
        except:
            pass

    return (best_i, peak_lpf_original, peak_time, peak_type)

# -----------------------------
# Export routines
# -----------------------------
def export_buckling_images(odb_path, output_dir, n_modes=1, views=None, scale=80.0, prefix="buckling"):
    if views is None:
        views = ['WebFront', 'Side', 'Iso']
    if not os.path.exists(odb_path):
        print("[buckling] ODB not found: %s" % odb_path)
        return False

    _ensure_dir(output_dir)
    print("[buckling] Opening ODB: %s" % odb_path)
    odb_path_abs = os.path.abspath(odb_path)

    # Integrate v2 advantages: more robust ODB opening logic
    odb_session = None
    for key in list(session.odbs.keys()):
        if odb_path_abs in key or key in odb_path_abs:
            odb_session = session.odbs[key]
            print("[buckling] Found existing ODB in session.odbs: %s" % key)
            break
    
    if odb_session is None:
        session.openOdb(name=odb_path_abs)
        time.sleep(WAIT_AFTER_OPEN_SEC)
        all_keys = list(session.odbs.keys())
        print("[buckling] session.odbs keys after open: %s" % str(all_keys))
        if odb_path_abs in all_keys:
            odb_session = session.odbs[odb_path_abs]
        elif len(all_keys) > 0:
            for key in all_keys:
                if odb_path_abs in key or os.path.basename(odb_path_abs) in key:
                    odb_session = session.odbs[key]
                    print("[buckling] Matched ODB by key: %s" % key)
                    break
            if odb_session is None:
                odb_session = list(session.odbs.values())[-1]
                print("[buckling] Using last ODB in session.odbs")
        else:
            raise Exception("Could not find ODB in session.odbs after opening")

    from odbAccess import openOdb
    odb_access = openOdb(path=odb_path_abs, readOnly=True)
    step_name = get_step_with_most_frames(odb_access)
    st = odb_access.steps[step_name]
    available = max(0, len(st.frames) - 1)
    n_modes = min(int(n_modes), available)
    if n_modes <= 0:
        print("[buckling] No modes available: frames=%d" % len(st.frames))
        odb_access.close()
        return False

    vp = setup_export_viewport()
    time.sleep(0.2)  # Wait for viewport to be ready
    vp.setValues(displayedObject=odb_session)
    time.sleep(0.3)  # Wait for displayedObject setup to complete (critical: GUI needs time)

    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    time.sleep(WAIT_AFTER_SETVIEW)
    vp.odbDisplay.commonOptions.setValues(deformationScaling=UNIFORM,
                                          uniformScaleFactor=float(scale),
                                          visibleEdges=FEATURE)
    time.sleep(WAIT_AFTER_SETVIEW)

    ok = True
    exported = 0

    print("[buckling] n_modes=%d, views=%s, step=%s" % (n_modes, str(views), step_name))

    # --- Var A: U magnitude (default, keep old naming) ---
    try:
        vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL,
                                         refinement=(INVARIANT, 'Magnitude'))
        print("[buckling] Set primary variable U Magnitude OK")
    except Exception as e:
        print("[buckling] ERROR setting primary variable: %s" % str(e))
        return False
    time.sleep(WAIT_AFTER_SETVAR)  # GUI mode: wait for variable setting and rendering

    for v in views:
        print("[buckling] Applying view: %s" % v)
        if not apply_view(vp, v):
            print("[buckling] WARNING: apply_view failed for %s" % v)
            continue
        for m in range(1, n_modes + 1):
            print("[buckling] Processing mode %d, view %s" % (m, v))
            try:
                vp.odbDisplay.setFrame(step=step_name, frame=m)
                time.sleep(WAIT_AFTER_SETFRAME)
                vp.view.fitView()
            except Exception as e:
                print("[buckling] ERROR setting frame: %s" % str(e))
                continue
            base = os.path.join(output_dir, "%s_%s_mode%02d" % (prefix, v, m))
            print("[buckling] Exporting to: %s" % base)
            if _export_with_legend(vp, base):
                exported += 1
                print("[buckling] Export OK for mode %d view %s" % (m, v))
            else:
                ok = False
                print("[buckling] Export FAILED for mode %d view %s" % (m, v))

    # --- Var B: U1 (Priority 2) ---
    if EXPORT_BUCKLING_U1:
        try:
            vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL,
                                             refinement=(COMPONENT, 'U1'))
            time.sleep(WAIT_AFTER_SETVAR)  # GUI mode: wait for variable setting and rendering
            for v in views:
                if not apply_view(vp, v):
                    continue
                for m in range(1, n_modes + 1):
                    vp.odbDisplay.setFrame(step=step_name, frame=m)
                    time.sleep(WAIT_AFTER_SETFRAME)
                    vp.view.fitView()
                    base = os.path.join(output_dir, "buckling_U1_%s_mode%02d" % (v, m))
                    if _export_with_legend(vp, base):
                        exported += 1
                    else:
                        ok = False
        except Exception as e:
            ok = False
            print("[buckling] U1 export failed: %s" % str(e))

    odb_access.close()
    time.sleep(WAIT_BEFORE_CLOSE_SEC)
    
    # GUI mode: don't close session.odbs here, leave to main script for unified closing

    print("[buckling] Exported %d PNG(s)" % exported)
    return ok and exported > 0

def export_riks_images(odb_path, output_dir, views=None, scale=1.0):
    if views is None:
        views = ['WebFront', 'Side', 'Iso']
    if not os.path.exists(odb_path):
        print("[riks] ODB not found: %s" % odb_path)
        return False

    _ensure_dir(output_dir)
    print("[riks] Opening ODB: %s" % odb_path)
    odb_path_abs = os.path.abspath(odb_path)

    # Integrate v2 advantages: more robust ODB opening logic
    odb_session = None
    for key in list(session.odbs.keys()):
        if odb_path_abs in key or key in odb_path_abs:
            odb_session = session.odbs[key]
            print("[riks] Found existing ODB in session.odbs: %s" % key)
            break
    
    if odb_session is None:
        session.openOdb(name=odb_path_abs)
        time.sleep(WAIT_AFTER_OPEN_SEC)
        all_keys = list(session.odbs.keys())
        print("[riks] session.odbs keys after open: %s" % str(all_keys))
        if odb_path_abs in all_keys:
            odb_session = session.odbs[odb_path_abs]
        elif len(all_keys) > 0:
            for key in all_keys:
                if odb_path_abs in key or os.path.basename(odb_path_abs) in key:
                    odb_session = session.odbs[key]
                    print("[riks] Matched ODB by key: %s" % key)
                    break
            if odb_session is None:
                odb_session = list(session.odbs.values())[-1]
                print("[riks] Using last ODB in session.odbs")
        else:
            raise Exception("Could not find ODB in session.odbs after opening")

    from odbAccess import openOdb
    odb_access = openOdb(path=odb_path_abs, readOnly=True)

    step_name = get_step_with_most_frames(odb_access)
    step = odb_access.steps[step_name]
    last_frame = len(step.frames) - 1
    if last_frame < 0:
        odb_access.close()
        return False

    # Decide frames to export
    frames_to_export = []
    if RIKS_FRAME_POLICY == 'peakLPF':
        peak_i, peak_lpf, peak_t, peak_type = find_peak_lpf_frame_index(odb_access, step_name)
        frames_to_export.append(('peakLPF', peak_i, peak_lpf, peak_t, peak_type))
        if EXPORT_RIKS_LAST_TOO:
            frames_to_export.append(('last', last_frame, None, None, None))
    else:
        frames_to_export.append(('last', last_frame, None, None, None))

    vp = setup_export_viewport()
    time.sleep(0.2)  # Wait for viewport to be ready
    vp.setValues(displayedObject=odb_session)
    time.sleep(0.3)  # Wait for displayedObject setup to complete

    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    time.sleep(WAIT_AFTER_SETVIEW)
    vp.odbDisplay.commonOptions.setValues(deformationScaling=UNIFORM,
                                          uniformScaleFactor=float(scale),
                                          visibleEdges=FEATURE)
    time.sleep(WAIT_AFTER_SETVIEW)

    ok = True
    exported = 0

    for frame_info in frames_to_export:
        tag = frame_info[0]
        fr_i = frame_info[1]
        peak_lpf = frame_info[2] if len(frame_info) > 2 else None
        peak_t = frame_info[3] if len(frame_info) > 3 else None
        peak_type = frame_info[4] if len(frame_info) > 4 else None
        
        if fr_i < 0:
            ok = False
            continue
        try:
            vp.odbDisplay.setFrame(step=step_name, frame=fr_i)
            time.sleep(WAIT_AFTER_SETFRAME)
        except Exception as e:
            ok = False
            print("[riks] setFrame failed (%s): %s" % (tag, str(e)))
            continue

        if tag == 'peakLPF':
            peak_desc = "Peak before drop" if peak_type == 'peak_before_drop' else "Global max fallback"
            print("[riks] Using %s LPF frame=%d, peakLPF=%s, time=%s" % (peak_desc, fr_i, str(peak_lpf), str(peak_t)))

        for v in views:
            if not apply_view(vp, v):
                continue

            # --- Stress Mises ---
            try:
                vp.odbDisplay.setPrimaryVariable(variableLabel='S', outputPosition=INTEGRATION_POINT,
                                                 refinement=(INVARIANT, 'Mises'))
                time.sleep(WAIT_AFTER_SETVAR)  # GUI mode: wait for variable setting and rendering
                vp.view.fitView()
                time.sleep(WAIT_AFTER_SETVIEW)
                base = os.path.join(output_dir, "riks_stress_mises_%s_%s" % (tag, v))
                if _export_with_legend(vp, base):
                    exported += 1
                else:
                    ok = False
            except Exception as e:
                ok = False
                print("[riks] Stress export exception (%s,%s): %s" % (tag, v, str(e)))

            # --- PEEQ ---
            try:
                vp.odbDisplay.setPrimaryVariable(variableLabel='PEEQ', outputPosition=INTEGRATION_POINT)
                time.sleep(WAIT_AFTER_SETVAR)  # GUI mode: wait for variable setting and rendering
                vp.view.fitView()
                time.sleep(WAIT_AFTER_SETVIEW)
                base = os.path.join(output_dir, "riks_peeq_%s_%s" % (tag, v))
                if _export_with_legend(vp, base):
                    exported += 1
                else:
                    ok = False
            except Exception as e:
                note_path = os.path.join(output_dir, "riks_peeq_%s_%s_NOT_AVAILABLE.txt" % (tag, v))
                try:
                    with open(note_path, "w") as f:
                        f.write("PEEQ not available.\nError: %s\n" % str(e))
                except:
                    pass
                print("[riks] PEEQ not available (%s,%s). Wrote: %s" % (tag, v, note_path))

            # --- U1 (Priority 2) ---
            if EXPORT_RIKS_U1:
                try:
                    vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL,
                                                     refinement=(COMPONENT, 'U1'))
                    time.sleep(WAIT_AFTER_SETVAR)  # GUI mode: wait for variable setting and rendering
                    vp.view.fitView()
                    time.sleep(WAIT_AFTER_SETVIEW)
                    base = os.path.join(output_dir, "riks_U1_%s_%s" % (tag, v))
                    if _export_with_legend(vp, base):
                        exported += 1
                    else:
                        ok = False
                except Exception as e:
                    ok = False
                    print("[riks] U1 export exception (%s,%s): %s" % (tag, v, str(e)))

    odb_access.close()
    time.sleep(WAIT_BEFORE_CLOSE_SEC)
    
    # GUI mode: don't close session.odbs here, leave to main script for unified closing

    print("[riks] Exported %d PNG(s)" % exported)
    return ok and exported > 0

# -----------------------------
# Command-line argument support (from single_case)
# -----------------------------
def export_single_case_from_args():
    """Export images for a single case from command line arguments (integrated from single_case)"""
    import os as os_module  # Avoid variable name conflict
    
    # Parse command line arguments
    # Abaqus viewer will consume the -- separator, so need intelligent parameter recognition
    # Expected parameter format: buckle.odb riks.odb output_dir [n_modes]
    args = sys.argv
    
    # Method 1: If -- separator exists, use parameters after separator
    if '--' in args:
        arg_idx = args.index('--') + 1
        cmd_args = args[arg_idx:]
    else:
        # 方法2：智能识别参数（过滤掉Abaqus的系统参数）
        # 从sys.argv中提取：.odb文件、输出目录、数字
        odb_paths = []
        output_dir = None
        n_modes_str = None
        
        for arg in args:
            # 跳过空字符串
            if not arg or arg.strip() == '':
                continue
            # 跳过以-开头的选项
            if arg.startswith('-'):
                continue
            # 跳过Abaqus可执行文件和系统参数
            if arg.endswith('.exe') or arg.startswith('script='):
                continue
            if arg in ('ON', 'OFF', 'viewer', 'cae', 'noGUI'):
                continue
            # Skip temporary directory paths
            if 'Temp' in arg and 'AppData' in arg:
                continue
            if 'SIMULIA' in arg or 'Abaqus' in arg:
                continue
            
            # Identify .odb files
            if arg.endswith('.odb'):
                odb_paths.append(arg)
            # Identify numbers (n_modes)
            elif arg.isdigit():
                n_modes_str = arg
            # Identify output directory (contains results or output, or relative path)
            elif 'results' in arg.lower() or 'output' in arg.lower() or 'LC' in arg:
                if output_dir is None:
                    output_dir = arg
        
        # Build cmd_args: [buckle_odb, riks_odb, output_dir, n_modes]
        cmd_args = []
        if len(odb_paths) >= 2:
            cmd_args.append(odb_paths[0])  # buckle_odb
            cmd_args.append(odb_paths[1])  # riks_odb
        elif len(odb_paths) == 1:
            cmd_args.append(odb_paths[0])  # Only one ODB
            cmd_args.append("")            # Other is empty
        
        if output_dir:
            cmd_args.append(output_dir)
        
        if n_modes_str:
            cmd_args.append(n_modes_str)
    
    print("[args] Parsed arguments: %s" % str(cmd_args))
    
    if len(cmd_args) < 3:
        print("[ERROR] Usage: abaqus viewer script=export_images.py -- <buckle_odb> <riks_odb> <output_dir> [n_modes]")
        print("[ERROR] Got %d arguments after filtering, need at least 3" % len(cmd_args))
        print("[ERROR] All args: %s" % str(args))
        return False
    
    buckle_odb_path = cmd_args[0] if len(cmd_args) > 0 and cmd_args[0] else ""
    riks_odb_path = cmd_args[1] if len(cmd_args) > 1 and cmd_args[1] else ""
    output_dir = cmd_args[2] if len(cmd_args) > 2 and cmd_args[2] else ""
    
    # Safely parse n_modes, use default value if cannot parse (export only first mode)
    n_modes = 1
    if len(cmd_args) > 3:
        try:
            n_modes = int(cmd_args[3])
        except (ValueError, TypeError):
            print("[WARN] Could not parse n_modes from '%s', using default 1" % cmd_args[3])
            n_modes = 1
    
    print("="*70)
    print("Single Case Export (Research Mode)")
    print("="*70)
    print("Buckle ODB: %s" % buckle_odb_path)
    print("Riks ODB  : %s" % riks_odb_path)
    print("Output Dir: %s" % output_dir)
    print("Modes     : %d" % n_modes)
    print("="*70)
    
    # Ensure output directory exists
    if output_dir and not os_module.path.exists(output_dir):
        os_module.makedirs(output_dir)
        print("[main] Created output directory: %s" % output_dir)
    
    buck_ok = False
    riks_ok = False
    
    # Export Buckling images
    if buckle_odb_path and os_module.path.exists(buckle_odb_path):
        print("\n[main] Exporting buckling images (research mode: U-Magnitude + U1, with legend)...")
        buck_ok = export_buckling_images(
            buckle_odb_path, output_dir, 
            n_modes=n_modes, views=['WebFront', 'Side', 'Iso'], scale=80.0
        )
    else:
        print("[main] Buckle ODB not found or empty: %s" % buckle_odb_path)
    
    # Export Riks images
    if riks_odb_path and os_module.path.exists(riks_odb_path):
        print("\n[main] Exporting riks images (research mode: peakLPF frame, Mises+PEEQ+U1, with legend)...")
        riks_ok = export_riks_images(
            riks_odb_path, output_dir,
                    views=['WebFront', 'Side', 'Iso'], scale=1.0
        )
    else:
        print("[main] Riks ODB not found or empty: %s" % riks_odb_path)
    
    print("\n" + "="*70)
    print("Export Summary: Buckling=%s, Riks=%s" % 
          ("OK" if buck_ok else "FAIL", "OK" if riks_ok else "FAIL"))
    print("="*70)
    
    # Write completion flag file
    done_flag_path = os.path.join(output_dir, '_EXPORT_DONE.txt')
    try:
        with open(done_flag_path, 'w') as f:
            f.write("Export completed at: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("Buckling: %s\n" % ("OK" if buck_ok else "FAIL"))
            f.write("Riks: %s\n" % ("OK" if riks_ok else "FAIL"))
    except:
        pass
    
    # GUI mode: Ensure all operations complete before closing
    print("\n[main] Ensuring all operations are complete...")
    time.sleep(3.0)  # Wait for all file writes to complete (GUI mode needs longer time)
    
    # Close all ODB files
    print("[main] Closing all ODB files...")
    try:
        odb_keys = list(session.odbs.keys())
        print("[main] Found %d open ODB files" % len(odb_keys))
        for key in odb_keys:
            try:
                session.odbs[key].close()
                print("[main] Closed ODB: %s" % str(key)[:80])
            except Exception as e:
                print("[main] Error closing ODB: %s" % str(e))
        time.sleep(1.0)  # Wait for ODB closing to complete
    except Exception as e:
        print("[main] Error getting ODB list: %s" % str(e))
    
    # GUI mode: Wait for all operations to complete, then force exit
    print("[main] Waiting for all file operations to complete...")
    time.sleep(2.0)  # Extra wait to ensure all file writes complete
    
    # Flush output buffers
    sys.stdout.flush()
    sys.stderr.flush()
    
    print("[main] Export completed. Closing Abaqus Viewer in 1 second...")
    time.sleep(1.0)  # Final wait to ensure all output is written
    
    try:
        # Use os._exit to force exit (works in GUI mode too)
        os_module._exit(0 if (buck_ok and riks_ok) else 1)
    except:
        # If os._exit fails, try sys.exit
        try:
            sys.exit(0 if (buck_ok and riks_ok) else 1)
        except:
            pass
    
    return buck_ok and riks_ok

# -----------------------------
# Auto-discovery main (批量模式)
# -----------------------------
def find_and_export_all_images():
    log_file_path = os.path.join(OUTPUT_DIR, "export_images_log.txt")
    _ensure_dir(OUTPUT_DIR)
    with open(log_file_path, "w") as log:
        log.write("="*70 + "\nAuto Export Images Log (integrated version)\n" + "="*70 + "\n\n")
        log.write("WORK_DIR=%s\nOUTPUT_DIR=%s\nTEMP_DIR=%s\nSHORT_DIR=%s\n\n" % (WORK_DIR, OUTPUT_DIR, TEMP_DIR, SHORT_DIR))
        log.write("EXPORT_WITH_LEGEND=%s (always ON)\nEXPORT_BUCKLING_U1=%s\nEXPORT_RIKS_U1=%s\nRIKS_FRAME_POLICY=%s\nEXPORT_RIKS_LAST_TOO=%s\n\n" %
                  (EXPORT_WITH_LEGEND, EXPORT_BUCKLING_U1, EXPORT_RIKS_U1, RIKS_FRAME_POLICY, EXPORT_RIKS_LAST_TOO))
        log.write("Engineering Peak LPF Parameters:\n")
        log.write("  LPF_DROP_RATIO=%s (drop threshold: %.0f%%)\n" % (LPF_DROP_RATIO, (1.0 - LPF_DROP_RATIO) * 100))
        log.write("  LPF_DROP_PERSIST_N=%s (persistent points for sustained drop)\n" % LPF_DROP_PERSIST_N)
        log.write("  LPF_MIN_PEAK_FRAC=%s (min peak fraction of global peak)\n" % LPF_MIN_PEAK_FRAC)
        log.write("  LPF_SMOOTH_WINDOW=%s (smoothing window, 1=no smoothing)\n\n" % LPF_SMOOTH_WINDOW)

        if not os.path.exists(OUTPUT_DIR):
            print("[main] OUTPUT_DIR not found: %s" % OUTPUT_DIR)
            return

        model_dirs = [d for d in os.listdir(OUTPUT_DIR)
                      if os.path.isdir(os.path.join(OUTPUT_DIR, d)) and not d.startswith(".")]

        buck_ok = 0
        riks_ok = 0

        for model_name in model_dirs:
            model_path = os.path.join(OUTPUT_DIR, model_name)
            case_dirs = [d for d in os.listdir(model_path)
                         if os.path.isdir(os.path.join(model_path, d)) and not d.startswith(".")]

            for case_name in case_dirs:
                case_path = os.path.join(model_path, case_name)

                # 查找ODB文件（支持新的简化目录结构）
                short_case_dir = model_name + '_' + case_name
                buckle_odb = os.path.join(TEMP_DIR, short_case_dir, "Job_Buckle_%s_%s.odb" % (model_name, case_name))
                riks_odb   = os.path.join(TEMP_DIR, short_case_dir, "Job_Riks_%s_%s.odb" % (model_name, case_name))
                
                # 如果新路径不存在，尝试旧路径
                if not os.path.exists(buckle_odb):
                    buckle_odb = os.path.join(TEMP_DIR, "Job_Buckle_%s_%s.odb" % (model_name, case_name))
                if not os.path.exists(riks_odb):
                    riks_odb = os.path.join(TEMP_DIR, "Job_Riks_%s_%s.odb" % (model_name, case_name))

                log.write("Model=%s Case=%s\n" % (model_name, case_name))
                log.write("  BuckleODB=%s\n" % buckle_odb)
                log.write("  RiksODB  =%s\n" % riks_odb)

                ok_b = False
                ok_r = False

                if os.path.exists(buckle_odb):
                    print("\n[main] Buckling export: %s / %s" % (model_name, case_name))
                    ok_b = export_buckling_images(buckle_odb, case_path, n_modes=1,
                                                  views=['WebFront','Side','Iso'], scale=80.0)
                    if ok_b: buck_ok += 1
                else:
                    print("[main] Buckle ODB missing, skip: %s" % buckle_odb)

                if os.path.exists(riks_odb):
                    print("\n[main] Riks export: %s / %s" % (model_name, case_name))
                    ok_r = export_riks_images(riks_odb, case_path, views=['WebFront','Side','Iso'], scale=1.0)
                    if ok_r: riks_ok += 1
                else:
                    print("[main] Riks ODB missing, skip: %s" % riks_odb)

                log.write("  Buckling=%s\n" % ("OK" if ok_b else "FAIL/SKIP"))
                log.write("  Riks=%s\n\n" % ("OK" if ok_r else "FAIL/SKIP"))

        # 格式化summary（使用.format()，兼容Python 2.7）
        summary = "\n{sep}\nSUMMARY\n  Buckling OK: {b}\n  Riks OK    : {r}\n  Log        : {p}\n{sep}\n".format(
            sep="="*70, b=buck_ok, r=riks_ok, p=log_file_path
        )
        print(summary)
        log.write(summary)

if __name__ == "__main__":
    # 调试：打印所有参数
    print("[DEBUG] sys.argv = %s" % str(sys.argv))
    print("[DEBUG] '--' in sys.argv = %s" % ('--' in sys.argv))
    
    # 检查是否通过命令行参数调用（单算例模式）
    # 方法1：检测'--'分隔符
    # 方法2：检测sys.argv中是否包含.odb文件路径（因为Abaqus viewer会吃掉'--'）
    has_separator = '--' in sys.argv
    has_odb_arg = any(arg.endswith('.odb') for arg in sys.argv)
    
    print("[DEBUG] has_separator='--': %s" % has_separator)
    print("[DEBUG] has_odb_arg: %s" % has_odb_arg)
    
    is_single_case_mode = has_separator or has_odb_arg
    
    if is_single_case_mode:
        # 单算例模式
        print("[DEBUG] Running in single case mode (command line arguments)")
        try:
            success = export_single_case_from_args()
            print("[DEBUG] export_single_case_from_args returned: %s" % success)
            # GUI模式：确保所有操作完成后再退出
            time.sleep(2.0)
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                os._exit(0 if success else 1)
            except:
                sys.exit(0 if success else 1)
        except Exception as e:
            print("[ERROR] Export failed with exception: %s" % str(e))
            import traceback
            traceback.print_exc()
            try:
                os._exit(1)
            except:
                sys.exit(1)
    else:
        # 批量模式：自动发现所有算例
        print("[DEBUG] Running in batch mode (auto-discovery)")
        print("="*70)
        print("Auto Export Images Script (Integrated Version)")
        print("="*70)
        print("WORK_DIR : %s" % WORK_DIR)
        print("OUTPUT   : %s" % OUTPUT_DIR)
        print("TEMP_DIR : %s" % TEMP_DIR)
        print("SHORTDIR : %s" % SHORT_DIR)
        print("CONFIG   : withLegend=%s (always ON), bucklingU1=%s, riksU1=%s, riksPolicy=%s, riksLastToo=%s"
              % (EXPORT_WITH_LEGEND, EXPORT_BUCKLING_U1, EXPORT_RIKS_U1, RIKS_FRAME_POLICY, EXPORT_RIKS_LAST_TOO))
        print("PEAK LPF : dropRatio=%.2f (%.0f%% drop), persistN=%d, minPeakFrac=%.2f, smoothWin=%d"
              % (LPF_DROP_RATIO, (1.0 - LPF_DROP_RATIO) * 100, LPF_DROP_PERSIST_N, LPF_MIN_PEAK_FRAC, LPF_SMOOTH_WINDOW))
        print("="*70 + "\n")

        find_and_export_all_images()

        # GUI模式下会自动退出，不需要显式退出

