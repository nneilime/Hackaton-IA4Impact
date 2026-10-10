"""Build Germany service and test it against a disposable PostgreSQL 17 database."""
import subprocess
import time
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    image='lpc-germany-adapter-germany:latest'
    subprocess.run(['docker','build','--tag',image,str(root)],check=True)
    cid=subprocess.check_output(['docker','run','--rm','--detach','--network','none',
        '--env','POSTGRES_HOST_AUTH_METHOD=trust','--env','POSTGRES_DB=germany_test','postgres:17'],text=True).strip()
    try:
        for _ in range(30):
            if subprocess.run(['docker','exec',cid,'pg_isready','-h','127.0.0.1','-U','postgres','-d','germany_test'],capture_output=True).returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Temporary PostgreSQL did not start')
        subprocess.run(['docker','exec','-i',cid,'psql','-X','-q','-U','postgres','-d','germany_test','-v','ON_ERROR_STOP=1'],
            input=(root/'tests/flat_schema.sql').read_text(),text=True,check=True)
        subprocess.run(['docker','run','--rm','--network','container:'+cid,
            '--env','TEST_DATABASE_URL=postgresql://postgres@127.0.0.1/germany_test',
            '--mount',f'type=bind,source={root},target=/test,readonly','--workdir','/test',
            image,'python','-m','unittest','discover','-s','tests','-v'],check=True)
        # Exercise the shipped CLI from the image, without its test bind mount.
        subprocess.run(['docker','run','--rm','--network','container:'+cid,
            '--env','DATABASE_URL=postgresql://postgres@127.0.0.1/germany_test',
            image,'python','main.py','--check-db'],stdout=subprocess.DEVNULL,check=True)
        print('PASS: Docker build, complete test suite and shipped --check-db interface')
    finally:
        subprocess.run(['docker','stop','--time','1',cid],check=True,capture_output=True)


if __name__=='__main__':main()
