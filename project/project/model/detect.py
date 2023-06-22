# YOLOv5 🚀 by Ultralytics, AGPL-3.0 license
"""
Run YOLOv5 detection inference on images, videos, directories, globs, YouTube, webcam, streams, etc.

Usage - sources:
    $ python detect.py --weights yolov5s.pt --source 0                               # webcam
                                                     img.jpg                         # image
                                                     vid.mp4                         # video
                                                     screen                          # screenshot
                                                     path/                           # directory
                                                     list.txt                        # list of images
                                                     list.streams                    # list of streams
                                                     'path/*.jpg'                    # glob
                                                     'https://youtu.be/Zgi9g1ksQHc'  # YouTube
                                                     'rtsp://example.com/media.mp4'  # RTSP, RTMP, HTTP stream

Usage - formats:
    $ python detect.py --weights yolov5s.pt                 # PyTorch
                                 yolov5s.torchscript        # TorchScript
                                 yolov5s.onnx               # ONNX Runtime or OpenCV DNN with --dnn
                                 yolov5s_openvino_model     # OpenVINO
                                 yolov5s.engine             # TensorRT
                                 yolov5s.mlmodel            # CoreML (macOS-only)
                                 yolov5s_saved_model        # TensorFlow SavedModel
                                 yolov5s.pb                 # TensorFlow GraphDef
                                 yolov5s.tflite             # TensorFlow Lite
                                 yolov5s_edgetpu.tflite     # TensorFlow Edge TPU
                                 yolov5s_paddle_model       # PaddlePaddle
"""

import argparse
import os
import platform
import sys
from pathlib import Path

import torch

import numpy as np
import time
import requests
import re
import threading

FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]  # YOLOv5 root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # relative

from models.common import DetectMultiBackend
from utils.dataloaders import IMG_FORMATS, VID_FORMATS, LoadImages, LoadScreenshots, LoadStreams
from utils.general import (LOGGER, Profile, check_file, check_img_size, check_imshow, check_requirements, colorstr, cv2,
                           increment_path, non_max_suppression, print_args, scale_boxes, strip_optimizer, xyxy2xywh)
from utils.plots import Annotator, colors, save_one_box
from utils.torch_utils import select_device, smart_inference_mode

@smart_inference_mode()
def run(
        weights=ROOT / 'yolov5s.pt',  # model path or triton URL
        source=ROOT / 'data/images',  # file/dir/URL/glob/screen/0(webcam)
        data=ROOT / 'data/coco128.yaml',  # dataset.yaml path
        imgsz=(640, 640),  # inference size (height, width)
        conf_thres=0.25,  # confidence threshold
        iou_thres=0.45,  # NMS IOU threshold
        max_det=1000,  # maximum detections per image
        device='',  # cuda device, i.e. 0 or 0,1,2,3 or cpu
        view_img=False,  # show results
        save_txt=False,  # save results to *.txt
        save_conf=False,  # save confidences in --save-txt labels
        save_crop=False,  # save cropped prediction boxes
        nosave=False,  # do not save images/videos
        classes=None,  # filter by class: --class 0, or --class 0 2 3
        agnostic_nms=False,  # class-agnostic NMS
        augment=False,  # augmented inference
        visualize=False,  # visualize features
        update=False,  # update all models
        project=ROOT / 'runs/detect',  # save results to project/name
        name='exp',  # save results to project/name
        exist_ok=False,  # existing project/name ok, do not increment
        line_thickness=3,  # bounding box thickness (pixels)
        hide_labels=False,  # hide labels
        hide_conf=False,  # hide confidences
        half=False,  # use FP16 half-precision inference
        dnn=False,  # use OpenCV DNN for ONNX inference
        vid_stride=1,  # video frame-rate stride
        cashier_id=0,
        auth_token=ROOT,
):
    source = str(source)
    save_img = not nosave and not source.endswith('.txt')  # save inference images
    is_file = Path(source).suffix[1:] in (IMG_FORMATS + VID_FORMATS)
    is_url = source.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://'))
    webcam = source.isnumeric() or source.endswith('.streams') or (is_url and not is_file)
    screenshot = source.lower().startswith('screen')
    if is_url and is_file:
        source = check_file(source)  # download

    # Directories
    save_dir = increment_path(Path(project) / name, exist_ok=exist_ok)  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Load model
    device = select_device(device)
    model = DetectMultiBackend(weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz, s=stride)  # check image size

    # Dataloader
    bs = 1  # batch_size
    if webcam:
        view_img = check_imshow(warn=True)
        dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
        bs = len(dataset)
    elif screenshot:
        dataset = LoadScreenshots(source, img_size=imgsz, stride=stride, auto=pt)
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
    vid_path, vid_writer = [None] * bs, [None] * bs

    # Run inference
    model.warmup(imgsz=(1 if pt or model.triton else bs, 3, *imgsz))  # warmup
    seen, windows, dt = 0, [], (Profile(), Profile(), Profile())
    
    predictedLabels_se = np.array([])
    startTime_se = time.time()
    noObjectCount = 0
    enter_coordinates = None
    exit_coordinates = None
    for path, im, im0s, vid_cap, s in dataset:
        with dt[0]:
            im = torch.from_numpy(im).to(model.device)
            im = im.half() if model.fp16 else im.float()  # uint8 to fp16/32
            im /= 255  # 0 - 255 to 0.0 - 1.0
            if len(im.shape) == 3:
                im = im[None]  # expand for batch dim

        # Inference
        with dt[1]:
            visualize = increment_path(save_dir / Path(path).stem, mkdir=True) if visualize else False
            pred = model(im, augment=augment, visualize=visualize)

        # NMS
        with dt[2]:
            pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det)

        # Second-stage classifier (optional)
        # pred = utils.general.apply_classifier(pred, classifier_model, im, im0s)

        #print(cashier_id)
        #print(auth_token)

        # Process predictions
        for i, det in enumerate(pred):  # per image 
            seen += 1
            if webcam:  # batch_size >= 1
                p, im0, frame = path[i], im0s[i].copy(), dataset.count
                s += f'{i}: '
            else:
                p, im0, frame = path, im0s.copy(), getattr(dataset, 'frame', 0)

            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # im.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # im.txt
            s += '%gx%g ' % im.shape[2:]  # print string
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            imc = im0.copy() if save_crop else im0  # for save_crop
            annotator = Annotator(im0, line_width=line_thickness, example=str(names))
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()


                

                # Print results
                for c in det[:, 5].unique():
                    n = (det[:, 5] == c).sum()  # detections per class
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string

                for *xyxy, conf, cls in reversed(det):
                    xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                    #print(*xywh)
                    x, y, w, h = xywh  # Giriş koordinatları (normalleştirilmiş xywh)

                    # Eğer giriş koordinatları daha önce belirlenmediyse, şu anki koordinatları giriş koordinatları olarak kabul et
                    if enter_coordinates is None and (0.1 <= x <= 0.9):
                        
                        enter_coordinates = (x, y)
                        #print(enter_coordinates)
                        #print('***---1')
                        noObjectCount = 0
                    # Eğer giriş koordinatları belirlendiyse, çıkış koordinatları olarak kabul et ve döngüyü sonlandır
                    else:
                        exit_coordinates = (x, y)
                        #print(exit_coordinates)
                        #print('***---2')
                        #break

                # item is detected, so send a request to decrease stock
                if enter_coordinates is not None and exit_coordinates is not None and (abs(exit_coordinates[0] - enter_coordinates[0]) >= 0.6):
                    difference = (exit_coordinates[0] - enter_coordinates[0], exit_coordinates[1] - enter_coordinates[1])
                    enter_coordinates = None
                    exit_coordinates = None

                    # İstek gönderilecek backend URL'si
                    url = "https://recognition-items-backend.up.railway.app/item/decrease"  
                    headers = {
                        "Authorization": f"Bearer {auth_token}"
                    }
                    # İstek gövdesi
                    thread = threading.Thread(target=send_request, args=(url, headers, cashier_id, s))
                    #print("thread is starting")
                    thread.start()
                   # thread.join()
                    
                    # pattern = r"\d:\s\d+x\d+\s\d+\s(.+?)(?=,)"

                    # match = re.search(pattern, s)

                    # if match:
                    #     result = match.group(1)
                    #     #print("result:")
                    #     #print(result)  # "Flormar HC28 Urban Escapes" çıktısını verecektir
                    #     data = {
                    #         "cashierId": cashier_id,
                    #         "itemName": result
                    #     }
                    #     response = requests.post(url, json=data, headers=headers)
                    #     print(response.status_code)
                    # # İstek gönderme
                    # #response = requests.post(url, json=data)
                    
                    #print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Movement Difference:", difference)
                    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Movement Difference: 0: 384x512 1 Capri-Sun Safari Fruits,
                    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Movement Difference: 0: 384x512 1 Rexona Roll On,
                    #print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Movement Difference: ", s, "  **")

                # Write results
                for *xyxy, conf, cls in reversed(det):
                    if save_txt:  # Write to file
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                        line = (cls, *xywh, conf) if save_conf else (cls, *xywh)  # label format
                        with open(f'{txt_path}.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or save_crop or view_img:  # Add bbox to image
                        c = int(cls)  # integer class
                        label = None if hide_labels else (names[c] if hide_conf else f'{names[c]} {conf:.2f}')
                        annotator.box_label(xyxy, label, color=colors(c, True))
                        
                        #productDetection();
                        predictedLabels_se = np.append(predictedLabels_se, label)
                        endTime_se = time.time()
                        #if endTime_se - startTime_se >= 2:
                        #    productDetection(predictedLabels_se)
                        #    predictedLabels_se = np.array([])
                        #    startTime_se = time.time()

                    if save_crop:
                        save_one_box(xyxy, imc, file=save_dir / 'crops' / names[c] / f'{p.stem}.jpg', BGR=True)

            # Stream results
            im0 = annotator.result()
            if view_img:
                if platform.system() == 'Linux' and p not in windows:
                    windows.append(p)
                    cv2.namedWindow(str(p), cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)  # allow window resize (Linux)
                    cv2.resizeWindow(str(p), im0.shape[1], im0.shape[0])
                cv2.imshow(str(p), im0)
                cv2.waitKey(1)  # 1 millisecond

            # Save results (image with detections)
            if save_img:
                if dataset.mode == 'image':
                    cv2.imwrite(save_path, im0)
                else:  # 'video' or 'stream'
                    if vid_path[i] != save_path:  # new video
                        vid_path[i] = save_path
                        if isinstance(vid_writer[i], cv2.VideoWriter):
                            vid_writer[i].release()  # release previous video writer
                        if vid_cap:  # video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        else:  # stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                        save_path = str(Path(save_path).with_suffix('.mp4'))  # force *.mp4 suffix on results videos
                        vid_writer[i] = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                    vid_writer[i].write(im0)

        # Print time (inference-only)
        #LOGGER.info(f"{s}{'' if len(det) else '(no detections), '}{dt[1].dt * 1E3:.1f}ms")
        if not len(det):
            noObjectCount += 1
            if noObjectCount >= 10 and enter_coordinates is not None:
                # print("**************************************************1noooooo:", noObjectCount)
                noObjectCount = 0
                enter_coordinates = None
                exit_coordinates = None

    # Print results
    t = tuple(x.t / seen * 1E3 for x in dt)  # speeds per image
    #LOGGER.info(f'Speed: %.1fms pre-process, %.1fms inference, %.1fms NMS per image at shape {(1, 3, *imgsz)}' % t)
    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ''
        #LOGGER.info(f"Results saved to {colorstr('bold', save_dir)}{s}")
    if update:
        strip_optimizer(weights[0])  # update model (to fix SourceChangeWarning)

def remove_plural(word):

    items_to_check = [
        "Ülker Salty Pretzels",
        "Doğadan Sage 20s",
        "Capri-Sun Safari Fruits"
    ]

    # if word.endswith('s') and not word.endswith('ss'):
    #     return word[:-1]
    # else:
    #     return word
    
    if word in items_to_check:
        if word.endswith("ss"):
            word = word[:-1]
    else: 
        word = word[:-1]
    
def send_request(url, headers, cashier_id, s):
    pattern = r"\d:\s\d+x\d+\s\d+\s(.+?)(?=,)"

    match = re.search(pattern, s)

    
    if match:
        result = match.group(1)
        remove_plural(result)
        #print("result:")
        print(result + " is detected. Sending request...")  # "Flormar HC28 Urban Escapes" çıktısını verecektir
        data = {
            "cashierId": cashier_id,
            "itemName": result
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print("Stock is decreased successfully.")
        else:
            print("Status code: " + str(response.status_code) + " Message: " + response.text)


class PredictedProducts:
    def __init__(self, productName, count=0, totalPred=0.0):
        self.productName=productName
        self.count = count
        self.totalPred = totalPred
    def set(self,count,totalPred):
        self.count += count
        self.totalPred+= totalPred
    def getName(self):
        return self.productName
    def getCount(self):
        return self.count
    def getTotalPred(self):
        return self.totalPred
    def getPred(self):
        pred_se = self.totalPred / self.count
        return self.productName, pred_se

def findProductIndex(predictedProducts, productName):
    for i in range (len(predictedProducts)):
        if predictedProducts[i].getName() == productName:
            return i
    return -1 

def findMaxTwoClass(predictedProducts):
    maxIndex1_se = 0
    maxIndex2_se = 0
    maxCount1_se = 0
    maxCount2_se = 0

    if  (len(predictedProducts)) == 2:
        return 0, 1
    
    for i in range (len(predictedProducts)):
        if predictedProducts[i].getCount() > maxCount1_se:
            maxCount1_se = predictedProducts[i].getCount()
            maxIndex1_se = i

        elif predictedProducts[i].getCount() > maxCount2_se:
            maxCount2_se = predictedProducts[i].getCount()
            maxIndex2_se = i
        
    return maxIndex1_se, maxIndex2_se

def productDetection(predictedLabels_se):
    #print("-----------------------------------------------------")
    #print(predictedLabels_se)
    
    products_se = []
    predictions_se = []
    predUniqueCls = []

    for item in predictedLabels_se:
        parts_se = item.split(' ') 
        product_se = ' '.join(parts_se[:-1]) 
        prediction_se = parts_se[-1]  
        if float(prediction_se) >= 0.50:
            products_se.append(product_se)
            predictions_se.append(prediction_se)

    # for i in range (len(predictions_se)):
    #     print("Product name:", products_se[i])
    #     print("Prediction:", predictions_se[i])
    #     print("---")   

    for i in range (len(products_se)):
        x = products_se[i]
        index = findProductIndex(predUniqueCls, x)
        if index == -1:
            predUniqueCls.append(PredictedProducts(x, 1, float(predictions_se[i])))
        else:
            predUniqueCls[index].set(1, float(predictions_se[i]))

    # for i in range (len(predUniqueCls)):
    #     print("*Product name:", predUniqueCls[i].getName())
    #     print("*Count:", predUniqueCls[i].getCount())
    #     print("*Total Prediction:", predUniqueCls[i].getTotalPred())
  
    if len(predUniqueCls) > 1:
        maxIndex1_se, maxIndex2_se = findMaxTwoClass(predUniqueCls)
        #print("--- " + str(maxIndex1_se) + " " + str(maxIndex2_se))

        if predUniqueCls[maxIndex1_se].getCount() - predUniqueCls[maxIndex2_se].getCount() > 3:
            tempoylesine = 3
            #print("------------------------------------------------------ " + predUniqueCls[maxIndex1_se].getName())
        else:
            maxName1_se, maxPred1_se = predUniqueCls[maxIndex1_se].getPred()
            maxName2_se, maxPred2_se = predUniqueCls[maxIndex2_se].getPred()
            maxPred_se = max(maxPred1_se, maxPred2_se)
            maxName_se = maxName1_se if maxPred_se == maxPred1_se else maxName2_se
            #print("------------------------------------------------------ " + maxName_se)
    elif len(predUniqueCls) == 1:
        #print("------------------------------------------------------ " + predUniqueCls[0].getName())
        tempoylesine = 3

def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default=ROOT / 'yolov5s.pt', help='model path or triton URL')
    parser.add_argument('--source', type=str, default=ROOT / 'data/images', help='file/dir/URL/glob/screen/0(webcam)')
    parser.add_argument('--data', type=str, default=ROOT / 'data/coco128.yaml', help='(optional) dataset.yaml path')
    parser.add_argument('--imgsz', '--img', '--img-size', nargs='+', type=int, default=[640], help='inference size h,w')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU threshold')
    parser.add_argument('--max-det', type=int, default=1000, help='maximum detections per image')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='show results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--save-crop', action='store_true', help='save cropped prediction boxes')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --classes 0, or --classes 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--visualize', action='store_true', help='visualize features')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default=ROOT / 'runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--line-thickness', default=3, type=int, help='bounding box thickness (pixels)')
    parser.add_argument('--hide-labels', default=False, action='store_true', help='hide labels')
    parser.add_argument('--hide-conf', default=False, action='store_true', help='hide confidences')
    parser.add_argument('--half', action='store_true', help='use FP16 half-precision inference')
    parser.add_argument('--dnn', action='store_true', help='use OpenCV DNN for ONNX inference')
    parser.add_argument('--vid-stride', type=int, default=1, help='video frame-rate stride')
    parser.add_argument('--cashier-id', type=int, default=0, help='cashier id')
    parser.add_argument('--auth-token', type=str, default=ROOT, help='auth token')
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    #print_args(vars(opt))
    return opt


def main(opt):
    check_requirements(ROOT / 'requirements.txt', exclude=('tensorboard', 'thop'))
    run(**vars(opt))


if __name__ == '__main__':
    opt = parse_opt()
    main(opt)
