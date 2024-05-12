import sys
from os import path

import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUiType
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import PCA
from FaceDetection import face_detection, draw_rectangle

FORM_CLASS, _ = loadUiType(
    path.join(path.dirname(__file__), "main.ui")
)  # connects the Ui file with the Python file


class MainApp(QMainWindow, FORM_CLASS):
    def __init__(self, parent=None):
        super(MainApp, self).__init__(parent)
        self.setupUi(self)
        self.handle_buttons()
        self.setWindowTitle("Face Detection")
        self.loaded_image = None
        self.image_with_faces = None
        self.file_path = None
        (self.training_principal_components, self.training_projected_data, self.training_images_not_flattened,
         self.training_image_paths, self.training_labels) = PCA.pca_analysis(
            "Dataset/Training"
        )
        self.testing_principal_components, self.testing_projected_data, self.testing_images_not_flattened, self.testing_image_paths, self.testing_labels = PCA.pca_analysis(
            "Dataset/Testing"
        )
        self.perform_pca()

    def handle_buttons(self):
        """
        Connects buttons to their respective functions and initializes the application.
        """
        self.label.mouseDoubleClickEvent = lambda event: self.handle_mouse(event, label=self.label)
        self.pushButton.clicked.connect(self.face_detection)
        self.pushButton_2.clicked.connect(self.recognize_face)
        self.recog_slider.valueChanged.connect(self.recognize_face_slider_change)

    def handle_mouse(self, event, label):
        """
        Method to handle the mouse click event on the image.

        Args:
            event: The mouse click event.
        """
        if event.button() == Qt.LeftButton:
            self.load_image(label)
        # elif event.button() == Qt.RightButton:
        #     self.detect_face()

    def load_image(self, label):
        """
        Method to load the image and display it on the GUI.
        """
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "",
                                                        "Image Files (*.png *.jpg *.jpeg *.bmp *.pgm)")
        self.loaded_image = cv2.imread(self.file_path)
        self.loaded_image = cv2.cvtColor(self.loaded_image, cv2.COLOR_BGR2RGB)
        self.display_image(self.loaded_image, label)

    def display_image(self, image, label):
        """
        Method to display the image on the GUI.

        Args:
            image: The image to be displayed.
        """

        height, width, channel = image.shape
        # Resize label to fit the image
        label.resize(width, height)
        bytesPerLine = 3 * width
        qImg = QImage(image.data, width, height, bytesPerLine, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qImg)
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)
        label.setScaledContents(True)
        label.show()

    def face_detection(self):
        """
        Method to detect the face in the image.
        """
        faces = face_detection(self.loaded_image)
        self.image_with_faces = draw_rectangle(self.loaded_image, faces)
        self.display_image(self.image_with_faces, self.label_2)

    def recognize_face(self):
        """
        Method to recognize the face in the image.
        """
        threshold = self.recog_slider.value()
        face_id = PCA.detect_faces(self.file_path, threshold, self.training_principal_components,
                                   self.training_projected_data, self.training_labels)
        if face_id not in [-1, None]:
            image = cv2.imread(self.training_image_paths[face_id])
            self.display_image(image, self.label_2)

        else:
            self.label_2.setText("Face not recognized")

        # self.display_image(image, self.label_2)

    def perform_pca(self):
        """
        Method to perform PCA on the images.
        """
        true_positive = 0
        false_positive = 0
        true_negative = 0
        false_negative = 0
        false_positive_rate = []
        true_positive_rate = []
        threshold = self.recog_slider.value()

        for i in range(len(self.testing_image_paths)):
            face_id = PCA.detect_faces(self.testing_image_paths[i], threshold, self.training_principal_components,
                                       self.training_projected_data, self.training_labels)
            if self.training_labels[face_id] == self.testing_labels[i] and face_id != -1:
                true_positive += 1
            elif self.training_labels[face_id] != self.testing_labels[i] and face_id != -1:
                false_positive += 1
            elif face_id == -1 and self.testing_labels[i] in self.training_labels:
                false_negative += 1
            else:
                true_negative += 1

            if true_negative + false_positive == 0:
                false_positive_rate.append(0)
                true_positive_rate.append(0)
            else:
                true_positive_rate.append(true_positive / (true_positive + false_negative))
                false_positive_rate.append(false_positive / (false_positive + true_negative))

        accuracy = (true_positive + true_negative) / (true_positive + true_negative + false_positive + false_negative)
        precision = true_positive / (true_positive + false_positive)
        recall = true_positive / (true_positive + false_negative)
        if true_negative + false_positive == 0:
            specificity = 0
            false_positive_rate_value = 0
        else:
            specificity = true_negative / (true_negative + false_positive)
            false_positive_rate_value = false_positive / (false_positive + true_negative)
        f1_score = 2 * (precision * recall) / (precision + recall)

        self.accuracy_lbl.setText("Accuracy : " + str(accuracy))
        self.precision_lbl.setText("Precision : " + str(precision))
        self.recall_lbl.setText("Recall : " + str(recall))
        self.specificity_lbl.setText("Specificity : " + str(specificity))
        self.false_positive_rate_lbl.setText("False Positive Rate : " + str(false_positive_rate_value))
        self.f1_score_lbl.setText("F1 Score : " + str(f1_score))

        # ROC Curve and AUC Score
        if len(false_positive_rate) > 0:
            auc_value = self.calculate_auc(false_positive_rate, true_positive_rate)
            self.auc_lbl.setText("AUC Score : " + str(auc_value))
            self.plot_roc_curve(false_positive_rate, true_positive_rate, auc_value)

    def calculate_auc(self, false_positive_rate, true_positive_rate):
        # Sort the TPR values in ascending order
        sorted_indices = sorted(range(len(false_positive_rate)), key=lambda i: false_positive_rate[i])
        sorted_fpr = [false_positive_rate[i] for i in sorted_indices]
        sorted_tpr = [true_positive_rate[i] for i in sorted_indices]

        auc_value = 0.0
        prev_fpr = 0.0
        prev_tpr = 0.0

        # Use the trapezoidal rule to calculate the area under the curve
        for fpr, tpr in zip(sorted_fpr, sorted_tpr):
            # Calculate the area of the trapezoid formed by the current and previous points
            auc_value += 0.5 * (fpr - prev_fpr) * (tpr + prev_tpr)

            # Update the previous FPR and TPR values for the next iteration
            prev_fpr = fpr
            prev_tpr = tpr

        return auc_value

    def plot_roc_curve(self, false_positive_rate, true_positive_rate, auc_value):
        """
        Method to plot the ROC curve on self.roc_lbl.
        """
        fig, ax = plt.subplots()
        ax.plot(false_positive_rate, true_positive_rate, label="ROC Curve")
        ax.plot([0, 1], [0, 1], linestyle="--", label="Random Guess")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("Receiver Operating Characteristic (ROC) Curve")
        ax.legend()

        # Create a canvas and draw the plot
        canvas = FigureCanvas(fig)
        canvas.draw()

        # Convert the canvas to a QPixmap and set it to the QLabel
        roc_pixmap = QPixmap(canvas.size())
        canvas.render(roc_pixmap)
        self.roc_lbl.setPixmap(roc_pixmap)



    def recognize_face_slider_change(self):
        self.recog_slider_lbl.setText("Recognition threshold : " + str(self.recog_slider.value()))
        self.perform_pca()


def main():
    """
    Method to start the application.

    Returns:
        None
    """
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    app.exec_()  # infinte Loop


if __name__ == "__main__":
    main()
