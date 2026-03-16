import traceback

try:
    from app import create_app
    app = create_app()
except Exception as e:
    err = traceback.format_exc()
    
    # A tiny WSGI app that just serves the exact startup crash trace
    def app(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [err.encode('utf-8')]

if __name__ == "__main__":
    try:
        app.run()
    except AttributeError:
        # Fallback if the real app failed to load
        pass
