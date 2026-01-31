from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import xml.etree.ElementTree as ET
from pathlib import Path

@dataclass(frozen=True)
class Box:
    xtl: float
    ytl: float
    xbr: float
    ybr: float
    rotation: float = 0.0
    plate_number: Optional[str] = None

def load_annotations(path: str) -> dict[str, list[Box]]:
    p = Path(path)
    if not p.exists():
        return {}

    tree = ET.parse(p)
    root = tree.getroot()

    out: dict[str, list[Box]] = {}
    for img in root.findall("image"):
        name = img.attrib.get("name")
        if not name:
            continue

        boxes: list[Box] = []
        for box in img.findall("box"):
            try:
                xtl = float(box.attrib["xtl"])
                ytl = float(box.attrib["ytl"])
                xbr = float(box.attrib["xbr"])
                ybr = float(box.attrib["ybr"])
                rotation = float(box.attrib.get("rotation", "0") or "0")
            except Exception:
                continue

            plate_number = None
            for attr in box.findall("attribute"):
                if attr.attrib.get("name") == "plate number":
                    plate_number = (attr.text or "").strip() or None

            boxes.append(Box(xtl=xtl, ytl=ytl, xbr=xbr, ybr=ybr, rotation=rotation, plate_number=plate_number))

        out[name] = boxes

    return out

def best_box_for_image(annotations: dict[str, list[Box]], filename: str) -> Optional[Box]:
    # najprościej: bierzemy pierwszy box (u Ciebie zwykle 1 tablica na obraz)
    boxes = annotations.get(filename)
    if not boxes:
        return None
    return boxes[0]

import xml.etree.ElementTree as ET
from typing import Optional

def gt_plate_for_image(xml_path: str, filename: str) -> Optional[str]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for img in root.findall(".//image"):
        if img.attrib.get("name") != filename:
            continue

        box = img.find(".//box[@label='plate']")
        if box is None:
            return None

        attr = box.find(".//attribute[@name='plate number']")
        if attr is None or attr.text is None:
            return None

        return attr.text.strip()

    return None


