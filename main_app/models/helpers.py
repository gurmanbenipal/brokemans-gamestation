import boto3
import os
import uuid

from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify

from . import Screenshot, File, Game


def boto3_client(service_name: str):
    """
        Get boto3 client with keys from the environment automatically added
    """
    return boto3.client(service_name,
                 aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                 aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])

def create_file(uploaded_file: UploadedFile, key: str) -> File:
    """
        Uploads a file on Amazon S3, returning its file model object
        Args:
            uploaded_file: the file to upload, retrieved from `request.FILES`
            key: the path to append to the base_url to upload the file to.
                e.g. "users/1/games/17/screenshots/xyz_my_file.png
        Returns:
            created File object
    """
    s3 = boto3_client("s3")
    bucket = os.environ["S3_BUCKET"]
    base_url = os.environ["S3_BASE_URL"]

    s3.upload_fileobj(uploaded_file, bucket, key)

    url = f"{base_url}{bucket}/{key}"

    return File.objects.create(url=url, key=key,
                mime_type=uploaded_file.content_type,
                filename=uploaded_file.name)


def get_fileext(uploaded_file: UploadedFile) -> str:
    if uploaded_file.name:
        return uploaded_file.name[uploaded_file.name.rfind("."):]
    else:
        return ""

def get_filename(uploaded_file: UploadedFile, prepend_hash=6) -> str:
    """
        Creates filename from UploadedFile, prepends 6 random characters to
        prevent file name collisions. If no name is provided to uploaded file,
        returns any empty string.
        Args:
            uploaded_file: file to get name from
            prepend_hash: number of hash characters to prepend filename with
        Returns:
            filename string
    """
    if uploaded_file.name:
        filename = (uuid.uuid4().hex[:prepend_hash] +
                    slugify(uploaded_file.name[:uploaded_file.name.rfind(".")]))
        filename += uploaded_file.name[uploaded_file.name.rfind("."):]
    else:
        return ""

    return filename



def create_screenshot(uploaded_file: UploadedFile, game_id: int) -> Screenshot | None:
    """
        Helper function to create a Screenshot from a file
        Url will be "user/<int:user_id>/games/<int:game_id>/screenshots/<6-char hash><filename><ext>"
        Args:
            uploaded_file: the file to upload, retrieved from `request.FILES`
            game_id: the game this screenshot is for
        Returns:
            Created Screenshot object on success, or None if game_id is invalid, or no filename
            retrieved from the `uploaded_file`
    """

    # get game to find user_id
    game = Game.objects.get(id=game_id)
    if not game:
        return None  # not a valid game

    user_id = game.user_id

    # get filename
    filename = get_filename(uploaded_file)
    if not filename:
        return None  # not a valid filename

    # get folder
    folder = "user/" + str(user_id) + "/games/" + str(game_id) + "/screenshots/"

    # create file
    file = create_file(uploaded_file, folder + filename)

    # attach file to new screenshot
    return Screenshot.objects.create(file=file, game_id=game_id)


def update_screenshot(screenshot_id: int, uploaded_file: UploadedFile):
    screenshot = Screenshot.objects.get(id=screenshot_id)

    if not screenshot:
        print("updated_screenshot error: invalid screenshot_id")
        return False  # not a valid screenshot

    # get folder
    folder = ("user/" + str(screenshot.game.user_id) + "/games/" +
              str(screenshot.game_id) + "/screenshots/")

    # get filename
    filename = get_filename(uploaded_file)
    if not filename:
        print("update_screenshot error: failed to get name from uploaded file")
        return False  # not a valid filename

    # create file
    file = create_file(uploaded_file, folder + filename)
    if not file:
        print("update_screenshot error: File failed to create")
        return False  # file failed to create

    # done -- replace file & commit
    screenshot.file.delete()
    screenshot.file = file
    screenshot.save()
    return True


def create_or_update_single_screenshot(uploaded_file: UploadedFile, game_id: int):
    """
        Create or update a Game's single screenshot
    """

    game = Game.objects.get(id=game_id)
    if not game:
        print("create_or_update_single_screenshot error: invalid game_id")
        return False

    if game.screenshot_set.count() > 0:
        screenshot = game.screenshot_set.first()
        screenshot.delete()

    screenshot = create_screenshot(uploaded_file, game_id)
    if not screenshot:
        print("create_or_update_single_screenshot error: failed to create_screenshot")
        return False
    game.screenshot_set.add(screenshot)

    return True