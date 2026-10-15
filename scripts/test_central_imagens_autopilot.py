import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import central_imagens


class AutomaticImageCurationGuardTests(unittest.TestCase):
    def test_cron_autopilot_stops_before_search_or_firestore_access(self):
        with patch.object(central_imagens, "buscar_google_images_playwright") as search:
            central_imagens.executar_curadoria(None, None, "5")
        search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
