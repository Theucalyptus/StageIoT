#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import threading, time, math
from queue import Queue
import json
import time
import sensors
import cv2, depthai as dai, numpy as np    # ← ton module
import logging

logger = logging.getLogger(__name__)

DEBUG_UI=True

# ---------- 1. Constantes tracking ----------------------------------------
PIX_MATCH_RADIUS   = 60    # px  – distance max centre‑à‑centre pour dire « même objet »
PIX_SEND_THRESHOLD = 40    # px  – déplacement min avant de ré‑émettre
LOST_TIMEOUT       = 2.0   # s   – purge si plus vu depuis X sec
SEND_PERIOD        = 5.0   # s   – cadence d’envoi

# ---------- 2. Objet suivi -------------------------------------------------
class Tracked:
    def __init__(self, obj_id, label, cx, cy, xyz):
        self.id       = obj_id
        self.label    = label
        self.cx, self.cy = cx, cy      # centre bbox (px)
        self.xyz      = xyz            # coords 3‑D (mm)
        self.last_sent_cxy = (cx, cy)  # dernière position transmise
        self.last_seen     = time.time()

    def moved_enough(self):
        return math.hypot(self.cx - self.last_sent_cxy[0],
                          self.cy - self.last_sent_cxy[1]) > PIX_SEND_THRESHOLD

    def update(self, cx, cy, xyz):
        self.cx, self.cy = cx, cy
        self.xyz = xyz
        self.last_seen = time.time()

#---------------------prepare the json------------------------------

#------ get latitude phone-----------
def get_latitude_longitude(lat, long, azimuthDeg, z, x):
    """
    Returns the latitude and longitude of the object, based on the azimuth and relative coordinates of the camera
    """
    z/=1000
    x/=1000
    aziTrig = (math.pi/2) - (azimuthDeg*math.pi/180)
    distLong = z*math.cos(aziTrig) + x*math.sin(aziTrig)
    distLat = z*math.sin(aziTrig) - x*math.cos(aziTrig)
    R = 6371000
    blat = distLat / (2*math.pi*R)
    blong = distLong / (2*math.pi*R)

    return lat+blat, long+blong

def construire_msg(tracked_objs, lat, long, azimuth):
    data = {
        "device-id": "jetson1",
        "type": 2,
        "timestamp": time.time(),
        "objects": []
    }

    for obj in tracked_objs:
        print(obj)                                              
                                                                #z          #x
        lat,lon= get_latitude_longitude(lat, long, azimuth, obj.xyz[2], obj.xyz[0])
        data["objects"].append({
            "latitude": lat,
            "longitude": lon,
            "label": obj.label,
            "id": obj.id
        })

    return data



# ---------- 3. Boucle principale ------------------------------------------
class Camera:

    def __init__(self):
        self.setCoordinates(0, 0, 0)
        self.stopVar = False
    
    def stop(self):
        self.stopVar = True
        self.thread.join()

    def run(self, q_netMain_in):
        self.thread = threading.Thread(target=self.ObjectDetection, args=(q_netMain_in,))
        self.thread.start()

    def setCoordinates(self, lat, long, azimuth):
        self.latitude = lat
        self.longitude = long
        self.azimuth = azimuth

    def ObjectDetection(self, Q_out: Queue):

        blob = Path(__file__).with_name("mobilenet-ssd_openvino_2021.4_6shave.blob")
        if not blob.exists():
            raise FileNotFoundError(blob)

        LABELS = ["background","aeroplane","bicycle","bird","boat","bottle","bus","car",
                "cat","chair","cow","diningtable","dog","horse","motorbike","person",
                "pottedplant","sheep","sofa","train","tvmonitor"]
        IMPORTANT = {"bicycle","bus","car","horse","motorbike","person"}

        # ---- pipeline ---------------------------------------------------
        pipe = dai.Pipeline()
        cam, monoL, monoR = pipe.create(dai.node.ColorCamera), pipe.create(dai.node.MonoCamera), pipe.create(dai.node.MonoCamera)
        stereo, nn        = pipe.create(dai.node.StereoDepth), pipe.create(dai.node.MobileNetSpatialDetectionNetwork)
        xout_rgb, xout_det = pipe.create(dai.node.XLinkOut), pipe.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb"); xout_det.setStreamName("det")
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

        cam.setPreviewSize(300,300); cam.setInterleaved(False)
        monoL.setCamera("left"); monoR.setCamera("right")
        nn.setBlobPath(str(blob)); nn.setConfidenceThreshold(0.5)
        monoL.out.link(stereo.left); monoR.out.link(stereo.right)
        cam.preview.link(nn.input); stereo.depth.link(nn.inputDepth)
        nn.out.link(xout_det.input); nn.passthrough.link(xout_rgb.input)

        # ---- tables de tracking -----------------------------------------
        next_id = 0
        tracked = {}      # id -> Tracked

        try:
            with dai.Device(pipe, maxUsbSpeed=dai.UsbSpeed.HIGH) as dev:
                q_rgb = dev.getOutputQueue("rgb",4,False)
                q_det = dev.getOutputQueue("det",4,False)

                t_last_send = time.time()

                while not self.stopVar:
                    rgb_msg = q_rgb.tryGet()
                    det_msg = q_det.tryGet()
                    if rgb_msg is None or det_msg is None:
                        time.sleep(0.002)
                        continue

                    frame = rgb_msg.getCvFrame()
                    detections = det_msg.detections
                    H,W = frame.shape[:2]
                    now = time.time()

                    # --------- association bbox -> tracked --------------------
                    matched_ids = set()
                    for d in detections:
                        label = LABELS[d.label] if d.label < len(LABELS) else str(d.label)
                        cx = int((d.xmin + d.xmax) / 2 * W)
                        cy = int((d.ymin + d.ymax) / 2 * H)
                        xyz = (d.spatialCoordinates.x, d.spatialCoordinates.y, d.spatialCoordinates.z)

                        # cherche le tracked du même label le plus proche
                        best, best_dist = None, 1e9
                        for tr in tracked.values():
                            if tr.label == label:
                                dist = math.hypot(cx - tr.cx, cy - tr.cy)
                                if dist < best_dist:
                                    best, best_dist = tr, dist
                        
                        if best and best_dist < PIX_MATCH_RADIUS:
                            best.update(cx, cy, xyz)
                            matched_ids.add(best.id)
                            trk = best
                            #print(f"[UPDATE] Objet ID {trk.id} ({label}) mis à jour à ({cx}, {cy})")
                        else:
                            trk = Tracked(next_id, label, cx, cy, xyz)
                            tracked[next_id] = trk
                            matched_ids.add(next_id)
                            #print(f"[NOUVEAU] Objet ID {next_id} ({label}) détecté à ({cx}, {cy})")
                            next_id += 1

                        if DEBUG_UI:
                            # dessin debug
                            x1,y1 = int(d.xmin*W), int(d.ymin*H)
                            x2,y2 = int(d.xmax*W), int(d.ymax*H)
                            cv2.rectangle(frame,(x1,y1),(x2,y2),(255,0,0),1)
                            cv2.putText(frame,f"ID {trk.id} d{trk.xyz[2]}", (x1,y1-4), cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,255,0))
                            cv2.putText(frame,label,(x1,y1+14),cv2.FONT_HERSHEY_SIMPLEX,0.5,255)

                    # --------- purge des perdus --------------------------------
                    for oid in list(tracked):
                        if now - tracked[oid].last_seen > LOST_TIMEOUT:
                            tracked.pop(oid)

                    # --------- envoi groupé périodique -------------------------
                    if now - t_last_send >= SEND_PERIOD:
                        
                        for tr in tracked.values():
                            if tr.label in IMPORTANT and tr.moved_enough():
                                x,y,z = tr.xyz
                                #payload += f"{tr.id:<3},{int(x):<6},{int(y):<6},{int(z):<6},{tr.label:<10};"
                                tr.last_sent_cxy = (tr.cx, tr.cy)
                        
                        if len(tracked.values()) > 0:
                            obj_data_msg = construire_msg(tracked.values(), self.latitude, self.longitude, self.azimuth)
                            print("envoi de données objets", obj_data_msg)
                            Q_out.put(obj_data_msg)
                            t_last_send = now

                    if DEBUG_UI:
                        cv2.imshow("preview", frame)
                        if cv2.waitKey(1) == ord('q'):
                            break
        except (ConnectionError, RuntimeError):
            logger.error("Failed to connect with the camera. Please check that the camera is properly plugged-in and restart the program, or disable it in the configuration.")
            logger.info("The program will continue but object detection will not function.")
        
# --------------- main thread -----------------------------------------------
if __name__ == "__main__":
    q = Queue()
    threading.Thread(target=Camera().bjectDetection,args=(q,),daemon=True).start()
    try:
        while True:
            print(q.get())
    except KeyboardInterrupt:
        print("Fin.")
