import torch
import model.model as module_arch
from utils3d import Utils3D
from utils3d import Render3D
from prediction import Predict2D


class DeepMVLM:
    def __init__(self, config):
        self.config = config
        self.device, self.model = self._get_device_and_load_model()
        self.logger = config.get_logger('predict')

    def _prepare_device(self, n_gpu_use):
        n_gpu = torch.cuda.device_count()
        if n_gpu_use > 0 and n_gpu == 0:
            self.logger.warning("Warning: There\'s no GPU available on this machine,"
                                "prediction will be performed on CPU.")
            n_gpu_use = 0
        if n_gpu_use > n_gpu:
            self.logger.warning("Warning: The number of GPU\'s configured to use is {}, but only {} are available "
                                "on this machine.".format(n_gpu_use, n_gpu))
            n_gpu_use = n_gpu
        if n_gpu_use > 0 and torch.cuda.is_available() \
                and (torch.cuda.get_device_capability()[0] * 10 + torch.cuda.get_device_capability()[1] < 35):
            self.logger.warning("Warning: The GPU has lower CUDA capabilities than the required 3.5 - using CPU")
            n_gpu_use = 0
        device = torch.device('cuda:0' if n_gpu_use > 0 else 'cpu')
        list_ids = list(range(n_gpu_use))
        return device, list_ids

    def _get_device_and_load_model(self):
        logger = self.config.get_logger('test')

        print('Initialising model')
        model = self.config.initialize('arch', module_arch)
        # logger.info(model)

        print('Loading checkpoint')
        model_name = self.config['name']
        if model_name == "MVLMModel_DTU3D":
            image_channels = self.config['data_loader']['args']['image_channels']
            if image_channels == "geometry":
                check_point_name = 'saved/trained/MVLMModel_DTU3D_geometry.pth'
            elif image_channels == "RGB":
                check_point_name = 'saved/trained/MVLMModel_DTU3D_RGB_07092019.pth'
            elif image_channels == "depth":
                check_point_name = 'saved/trained/MVLMModel_DTU3D_Depth_19092019.pth'
            elif image_channels == "RGB+depth":
                check_point_name = 'saved/trained/MVLMModel_DTU3D_RGB+depth_20092019.pth'
            else:
                print('No model trained for ', model_name, ' with channels ', image_channels)
                return None, None
        elif model_name == 'MVLMModel_BU_3DFE':
            image_channels = self.config['data_loader']['args']['image_channels']
            if image_channels == "RGB":
                check_point_name = 'saved/trained/MVLMModel_BU_3DFE_RGB_24092019_6epoch.pth'
            else:
                print('No model trained for ', model_name, ' with channels ', image_channels)
                return None, None
        else:
            print('No model trained for ', model_name)
            return None

        logger.info('Loading checkpoint: {}'.format(check_point_name))

        device, device_ids = self._prepare_device(self.config['n_gpu'])

        checkpoint = torch.load(check_point_name, map_location=device)

        state_dict = checkpoint['state_dict']
        if len(device_ids) > 1:
            model = torch.nn.DataParallel(model, device_ids=device_ids)

        model.load_state_dict(state_dict)

        model = model.to(device)
        model.eval()
        return device, model

    def predict_one_file(self, file_name):
        render_3d = Render3D(self.config)
        image_stack, transform_stack = render_3d.render_3d_file(file_name)

        predict_2d = Predict2D(self.config, self.model, self.device)
        heatmap_maxima = predict_2d.predict_heatmaps_from_images(image_stack)

        u3d = Utils3D(self.config)
        u3d.heatmap_maxima = heatmap_maxima
        u3d.transformations_3d = transform_stack
        u3d.compute_lines_from_heatmap_maxima()
        #  u3d.visualise_one_landmark_lines(65)
        u3d.compute_all_landmarks_from_view_lines()
        u3d.project_landmarks_to_surface(file_name)

        return u3d.landmarks

    @staticmethod
    def write_landmarks_as_vtk_points(landmarks, file_name):
        Utils3D.write_landmarks_as_vtk_points_external(landmarks, file_name)


