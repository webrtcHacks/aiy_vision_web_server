# Function to standardize inference output of AIY models
import json                             # Format API output

# AIY requirements
from aiy.vision.models import object_detection, face_detection, image_classification

# return the appropriate model
def model_selector(argument):
    options = {
        "object": object_detection.model(),
        "face": face_detection.model(),
        "class": image_classification.model()
    }
    return options.get(argument, "nothing")


# helper class to convert inference output to JSON
class ApiObject(object):
    def __init__(self):
        self.name = "webrtcHacks AIY Vision Server REST API"
        self.version = "0.2.1"
        self.numObjects = 0
        self.objects = []

    def to_json(self):
        return json.dumps(self.__dict__)


def process_inference(model, result, params):

    output = ApiObject()

    # handler for the AIY Vision object detection model
    if model == "object":
        output.threshold = 0.3
        objects = object_detection.get_objects(result, output.threshold)

        for obj in objects:
            # print(object)
            item = {
                'name': 'object',
                'class_name': obj._LABELS[obj.kind],
                'score': obj.score,
                'x': obj.bounding_box[0] / params['width'],
                'y': obj.bounding_box[1] / params['height'],
                'width': obj.bounding_box[2] / params['width'],
                'height': obj.bounding_box[3] / params['height']
            }

            output.numObjects += 1
            output.objects.append(item)

    # handler for the AIY Vision face detection model
    elif model == "face":
        faces = face_detection.get_faces(result)

        for face in faces:
            # print(face)
            item = {
                'name': 'face',
                'score': face.face_score,
                'joy': face.joy_score,
                'x': face.bounding_box[0] / params['width'],
                'y': face.bounding_box[1] / params['height'],
                'width': face.bounding_box[2] / params['width'],
                'height': face.bounding_box[3] / params['height']
            }

            output.numObjects += 1
            output.objects.append(item)

    elif model == "class":
        output.threshold = 0.3
        classes = image_classification.get_classes(result)

        s = ""

        for (obj, prob) in classes:
            if prob > output.threshold:
                s += '%s=%1.2f\t|\t' % (obj, prob)

                item = {
                    'name': 'class',
                    'class_name': obj,
                    'score': prob
                }

                output.numObjects += 1
                output.objects.append(item)

        # print('%s\r' % s)

    return output
