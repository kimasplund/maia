"""
Web dashboard module for MAIA.
Provides a web interface for monitoring and managing the system.
"""
import aiohttp
from aiohttp import web
import jinja2
import aiohttp_jinja2
import json
import os
from typing import Dict, Any, List
import logging
from datetime import datetime
from ..utils.logging_utils import AsyncLogger
from ..database.storage import UserStorage, CommandStorage
from ..core.seal_tools_integration import SealToolsIntegration

_LOGGER = logging.getLogger(__name__)

class Dashboard:
    def __init__(self, app: web.Application,
                 user_storage: UserStorage,
                 command_storage: CommandStorage,
                 seal_tools: SealToolsIntegration):
        self.app = app
        self.user_storage = user_storage
        self.command_storage = command_storage
        self.seal_tools = seal_tools
        self.logger = AsyncLogger(__name__)
        
        # Setup template engine
        aiohttp_jinja2.setup(
            app,
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates')
            )
        )
        
        # Setup routes
        self.setup_routes()
        
        # Setup static files
        app.router.add_static(
            '/static/',
            os.path.join(os.path.dirname(__file__), 'static')
        )

    def setup_routes(self):
        """Setup dashboard routes."""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/users', self.users)
        self.app.router.add_get('/commands', self.commands)
        self.app.router.add_get('/analytics', self.analytics)
        self.app.router.add_get('/settings', self.settings)
        
        # API routes
        self.app.router.add_get('/api/stats', self.api_stats)
        self.app.router.add_get('/api/users', self.api_users)
        self.app.router.add_get('/api/commands', self.api_commands)
        self.app.router.add_post('/api/settings', self.api_settings)

    @aiohttp_jinja2.template('index.html')
    async def index(self, request: web.Request) -> Dict[str, Any]:
        """Render dashboard index page."""
        try:
            # Get system stats
            stats = await self._get_system_stats()
            
            # Get recent activity
            recent_commands = await self.command_storage.get_user_history(
                "all",
                limit=10
            )
            
            # Get active users
            active_users = await self.user_storage.get_active_users(days=1)
            
            return {
                'page': 'dashboard',
                'stats': stats,
                'recent_commands': recent_commands,
                'active_users': active_users
            }
            
        except Exception as e:
            _LOGGER.error(f"Error rendering index: {str(e)}")
            return {'error': str(e)}

    @aiohttp_jinja2.template('users.html')
    async def users(self, request: web.Request) -> Dict[str, Any]:
        """Render users management page."""
        try:
            # Get all active users
            users = await self.user_storage.get_active_users(days=30)
            
            # Get user stats
            stats = await self._get_user_stats()
            
            return {
                'page': 'users',
                'users': users,
                'stats': stats
            }
            
        except Exception as e:
            _LOGGER.error(f"Error rendering users: {str(e)}")
            return {'error': str(e)}

    @aiohttp_jinja2.template('commands.html')
    async def commands(self, request: web.Request) -> Dict[str, Any]:
        """Render commands history page."""
        try:
            # Get command history
            history = await self.command_storage.get_user_history(
                "all",
                limit=50
            )
            
            # Get command stats
            stats = await self._get_command_stats()
            
            return {
                'page': 'commands',
                'history': history,
                'stats': stats
            }
            
        except Exception as e:
            _LOGGER.error(f"Error rendering commands: {str(e)}")
            return {'error': str(e)}

    @aiohttp_jinja2.template('analytics.html')
    async def analytics(self, request: web.Request) -> Dict[str, Any]:
        """Render analytics page."""
        try:
            # Get Seal Tools metrics
            seal_metrics = await self.seal_tools.get_metrics()
            
            # Get optimization status
            optimization_status = await self.seal_tools.get_optimization_status()
            
            # Get system performance metrics
            performance = await self._get_performance_metrics()
            
            return {
                'page': 'analytics',
                'seal_metrics': seal_metrics,
                'optimization_status': optimization_status,
                'performance': performance
            }
            
        except Exception as e:
            _LOGGER.error(f"Error rendering analytics: {str(e)}")
            return {'error': str(e)}

    @aiohttp_jinja2.template('settings.html')
    async def settings(self, request: web.Request) -> Dict[str, Any]:
        """Render settings page."""
        try:
            # Get current settings
            settings = await self._get_settings()
            
            return {
                'page': 'settings',
                'settings': settings
            }
            
        except Exception as e:
            _LOGGER.error(f"Error rendering settings: {str(e)}")
            return {'error': str(e)}

    async def api_stats(self, request: web.Request) -> web.Response:
        """API endpoint for system stats."""
        try:
            stats = await self._get_system_stats()
            return web.json_response(stats)
        except Exception as e:
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def api_users(self, request: web.Request) -> web.Response:
        """API endpoint for user data."""
        try:
            users = await self.user_storage.get_active_users()
            return web.json_response({'users': users})
        except Exception as e:
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def api_commands(self, request: web.Request) -> web.Response:
        """API endpoint for command history."""
        try:
            history = await self.command_storage.get_user_history("all")
            return web.json_response({'commands': history})
        except Exception as e:
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def api_settings(self, request: web.Request) -> web.Response:
        """API endpoint for updating settings."""
        try:
            data = await request.json()
            # Update settings
            success = await self._update_settings(data)
            return web.json_response({'success': success})
        except Exception as e:
            return web.json_response(
                {'error': str(e)},
                status=500
            )

    async def _get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            # Get various stats
            active_users = len(await self.user_storage.get_active_users(days=1))
            
            # Get command counts
            total_commands = 0  # This should be implemented
            successful_commands = 0  # This should be implemented
            
            # Get performance metrics
            performance = await self._get_performance_metrics()
            
            return {
                'active_users': active_users,
                'total_commands': total_commands,
                'successful_commands': successful_commands,
                'success_rate': (successful_commands / total_commands * 100
                               if total_commands > 0 else 0),
                'performance': performance
            }
            
        except Exception as e:
            _LOGGER.error(f"Error getting system stats: {str(e)}")
            return {}

    async def _get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics."""
        try:
            # Get user activity stats
            active_today = len(await self.user_storage.get_active_users(days=1))
            active_week = len(await self.user_storage.get_active_users(days=7))
            active_month = len(await self.user_storage.get_active_users(days=30))
            
            return {
                'active_today': active_today,
                'active_week': active_week,
                'active_month': active_month
            }
            
        except Exception as e:
            _LOGGER.error(f"Error getting user stats: {str(e)}")
            return {}

    async def _get_command_stats(self) -> Dict[str, Any]:
        """Get command statistics."""
        try:
            # This should be implemented to get actual stats
            return {
                'total_commands': 0,
                'successful_commands': 0,
                'failed_commands': 0,
                'average_response_time': 0
            }
        except Exception as e:
            _LOGGER.error(f"Error getting command stats: {str(e)}")
            return {}

    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        try:
            # Get metrics from logger
            metrics = await self.logger.get_performance_metrics()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics
            }
            
        except Exception as e:
            _LOGGER.error(f"Error getting performance metrics: {str(e)}")
            return {}

    async def _get_settings(self) -> Dict[str, Any]:
        """Get current system settings."""
        try:
            # This should be implemented to get actual settings
            return {
                'voice_processing': {
                    'enabled': True,
                    'advanced_mode': False
                },
                'face_recognition': {
                    'enabled': True,
                    'min_confidence': 0.8
                },
                'optimization': {
                    'enabled': True,
                    'interval': 3600
                }
            }
        except Exception as e:
            _LOGGER.error(f"Error getting settings: {str(e)}")
            return {}

    async def _update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update system settings."""
        try:
            # This should be implemented to update actual settings
            return True
        except Exception as e:
            _LOGGER.error(f"Error updating settings: {str(e)}")
            return False 