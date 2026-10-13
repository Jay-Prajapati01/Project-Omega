"""Apply the URL guard before browser requests, including redirected subresources."""
import asyncio
from app.core.ssrf import validate_public_url


async def protect_context(context):
    async def route_request(route):
        try:
            await asyncio.to_thread(validate_public_url, route.request.url)
        except (ValueError, OSError):
            await route.abort()
            return
        await route.continue_()
    await context.route("**/*", route_request)


async def crawler_hook(page, context, **kwargs):
    await protect_context(context)
    return page
