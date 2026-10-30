import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from scanner import enhance, export_pdf, load_image


class ScannerTests(unittest.TestCase):
    def test_cleanup_removes_shadow_and_preserves_text(self):
        gradient = np.tile(np.linspace(100, 230, 400), (300, 1))
        gradient[130:145, 50:350] = 15
        image = Image.fromarray(gradient.astype('uint8')).convert('RGB')
        result = np.asarray(enhance(image, strength=100))[:, :, 0]
        self.assertGreater(float(result[20:80].mean()), 235)
        self.assertLess(float(result[132:142, 60:340].mean()), 50)
        self.assertLess(float(result[20:80].std()), 15)

    def test_binary_and_original(self):
        image = Image.new('RGB', (80, 100), (120, 80, 50))
        self.assertEqual(enhance(image, 'Original').tobytes(), image.tobytes())
        self.assertTrue(set(np.unique(np.asarray(enhance(image, 'Black & white')))) <= {0, 255})

    def test_import_and_multipage_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            Image.new('RGB', (90, 120), 'white').save(path / 'source.png')
            image = load_image(path / 'source.png')
            export_pdf([image, image], path / 'scan.pdf')
            data = (path / 'scan.pdf').read_bytes()
            self.assertTrue(data.startswith(b'%PDF-'))
            self.assertIn(b'/Count 2', data)
            self.assertIn(b'%%EOF', data)

    def test_empty_export_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'existing.pdf'
            path.write_bytes(b'keep me')
            with self.assertRaises(ValueError):
                export_pdf([], path)
            self.assertEqual(path.read_bytes(), b'keep me')


if __name__ == '__main__':
    unittest.main()
