from app.services.lastfm import build_lastfm_api_sig


def main():
    params = {
        "api_key": "test_key",
        "method": "auth.getSession",
        "token": "test_token",
        "format": "json",
    }
    api_secret = "test_secret"

    signature = build_lastfm_api_sig(params, api_secret)

    print("Params:", params)
    print("Signature:", signature)


if __name__ == "__main__":
    main()