import unittest
from src.main import main

class TestMain(unittest.TestCase):
    def test_main(self):
        main()

if __name__ == "__main__":
    unittest.main()
```

[CMD]
```bash
git add .
git commit -m "Initial commit"
git push origin main
