# visualization.py

import cv2


def draw_accept_reject_overlay(image, spots):

    out = image.copy()

    for s in spots:

        bad = s.get("is_bad",False)

        color = (0,0,255) if bad else (255,0,0)

        cv2.drawContours(out,[s["contour"]],-1,color,2)

        cx,cy = s["center"]

        cv2.circle(out,(cx,cy),3,(0,0,255),-1)

        if "label" in s:

            cv2.putText(
                out,
                s["label"],
                (cx+5,cy-5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )

    return out