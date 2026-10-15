# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Executa les proves e2e.

    python e2e/run_e2e.py            # fa servir el build existent de webapp/dist
    python e2e/run_e2e.py --build    # compila l'Angular abans

Cal tenir instal·lades les dependències del servidor i les de e2e/requirements.txt,
i el navegador de Playwright (python -m playwright install chromium).
"""

import argparse
import os
import shutil
import subprocess
import sys
import unittest

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(E2E_DIR, '..', 'webapp')


def build_webapp():
    npm = shutil.which('npm') or shutil.which('npm.cmd')
    if npm is None:
        raise SystemExit("No s'ha trobat npm per compilar l'Angular.")
    print('Compilant l\'Angular…')
    subprocess.run([npm, 'run', 'build'], cwd=WEBAPP_DIR, check=True)


def main():
    parser = argparse.ArgumentParser(description='Proves e2e de KoraAccess')
    parser.add_argument('--build', action='store_true', help='compila l\'Angular abans')
    parser.add_argument('-k', dest='pattern', help='executa només les proves que continguin aquest text')
    args = parser.parse_args()

    if args.build:
        build_webapp()

    sys.path.insert(0, E2E_DIR)
    loader = unittest.TestLoader()
    if args.pattern:
        loader.testNamePatterns = [f'*{args.pattern}*']
    suite = loader.discover(E2E_DIR, pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
