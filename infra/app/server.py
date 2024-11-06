import joke
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    # Return raw HTML
    return "<h1>" + joke.tell_joke() + "</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)