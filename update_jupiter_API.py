import os
import requests


def main():

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Make the request using the CA bundle
    #r = requests.post("https://www.deadlypanda.com/positions/update_jupiter", verify=False)
    r = requests.post("http://127.0.0.1:5000/positions/update_jupiter", verify=False)

    print(r.status_code, r.text)


if __name__ == "__main__":
    main()
