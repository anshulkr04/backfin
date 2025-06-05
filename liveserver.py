#!/usr/bin/env python3
from flask import Flask, request, jsonify
import os
from gevent import monkey
# monkey.patch_all()
import sys
from functools import wraps
from flask_cors import CORS
from dotenv import load_dotenv
import datetime
import uuid
import logging
import hashlib
import secrets
import json
import threading
import importlib.util
from pathlib import Path
from flask_socketio import SocketIO, emit
import time
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('finBack')

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure CORS to be completely permissive
CORS(app, resources={
    r"/*": {
        "origins": "*", 
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], 
        "allow_headers": "*"
    }
}, supports_credentials=True)
# Initialize Socket.IO with the Flask app
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='eventlet',  # Use eventlet instead of gevent
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,
    transports=['websocket', 'polling']
)

# Improved Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections with improved logging"""
    client_id = request.sid
    ip = request.remote_addr if hasattr(request, 'remote_addr') else 'unknown'
    logger.info(f"Client connected: {client_id} from {ip}")
    
    # Send welcome message
    emit('status', {'message': 'Connected to Financial Backend API', 'connected': True})
    
    # Automatically join the 'all' room to receive general announcements
    socketio.server.enter_room(client_id, 'all')
    logger.info(f"Client {client_id} automatically joined room: all")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnections with improved logging"""
    client_id = request.sid
    logger.info(f"Client disconnected: {client_id}")

@socketio.on('error')
def handle_error(error):
    """Handle WebSocket errors"""
    client_id = request.sid
    logger.error(f"Socket error for client {client_id}: {error}")
    emit('status', {'message': 'Error occurred', 'error': True}, room=client_id)

@socketio.on('join')
def handle_join(data):
    """Handle client joining a specific room with improved validation"""
    client_id = request.sid
    
    # Validate room parameter
    if not isinstance(data, dict) or 'room' not in data:
        logger.warning(f"Invalid join request from {client_id}: missing 'room' parameter")
        emit('status', {'message': 'Invalid request: missing room parameter', 'error': True}, room=client_id)
        return
        
    room = data['room']
    
    # Validate room name
    if not room or not isinstance(room, str):
        logger.warning(f"Invalid join request from {client_id}: invalid room name")
        emit('status', {'message': 'Invalid request: invalid room name', 'error': True}, room=client_id)
        return
        
    # Sanitize room name (prevent injection)
    room = room.strip()[:50]  # Limit length and strip whitespace
    
    logger.info(f"Client {client_id} joined room: {room}")
    socketio.server.enter_room(client_id, room)
    emit('status', {'message': f'Joined room: {room}'}, room=client_id)

@socketio.on('leave')
def handle_leave(data):
    """Handle client leaving a specific room with improved validation"""
    client_id = request.sid
    
    # Validate room parameter
    if not isinstance(data, dict) or 'room' not in data:
        logger.warning(f"Invalid leave request from {client_id}: missing 'room' parameter")
        emit('status', {'message': 'Invalid request: missing room parameter', 'error': True}, room=client_id)
        return
        
    room = data['room']
    
    # Validate room name
    if not room or not isinstance(room, str):
        logger.warning(f"Invalid leave request from {client_id}: invalid room name")
        emit('status', {'message': 'Invalid request: invalid room name', 'error': True}, room=client_id)
        return
        
    # Sanitize room name
    room = room.strip()[:50]
    
    logger.info(f"Client {client_id} left room: {room}")
    socketio.server.leave_room(client_id, room)
    emit('status', {'message': f'Left room: {room}'}, room=client_id)


# Configuration options with environment variables
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
PORT = int(os.getenv('PORT', 5001))

# Set higher log level if debug mode is enabled
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

# Initialize Supabase client (for database operations only, not auth)
supabase = None
supabase_connected = False

try:
    from supabase import create_client, Client
    
    # Initialize Supabase client
    supabase_url = os.getenv('SUPABASE_URL2')
    supabase_key = os.getenv('SUPABASE_KEY2')
    
    if not supabase_url or not supabase_key:
        logger.error("Supabase credentials are missing! All data operations will fail.")
    else:
        logger.info(f"Initializing Supabase client with URL: {supabase_url[:20]}...")
        supabase = create_client(supabase_url, supabase_key)
        supabase_connected = True
        logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    logger.error("The application will not function correctly without Supabase.")

# Helper functions for custom auth
def hash_password(password):
    """Hash a password for storing."""
    salt = os.getenv('PASSWORD_SALT', 'default_salt_change_this_in_production')
    return hashlib.sha256((password + salt).encode()).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against a provided password."""
    return stored_password == hash_password(provided_password)

def generate_access_token():
    """Generate a secure random access token."""
    return secrets.token_hex(32)  # 64 character hex string

# Custom authentication middleware
def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Handle OPTIONS requests first
        if request.method == 'OPTIONS':
            return _handle_options()
            
        token = None
        
        # Check if token is in the request headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Authentication token is missing!'}), 401
        
        if not supabase_connected:
            return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
        
        try:
            # Find user with matching access token
            response = supabase.table('UserData').select('*').eq('AccessToken', token).execute()
            
            if not response.data or len(response.data) == 0:
                return jsonify({'message': 'Invalid authentication token!'}), 401
                
            # User found with matching token
            current_user = response.data[0]
            
            # Check if token is expired (optional - implement if needed)
            # You could add token_expiry field to UserData table
            
            return f(current_user, *args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return jsonify({'message': f'Authentication failed: {str(e)}'}), 401
    
    return decorated

def get_users_by_isin(isin):
    """Get users by ISIN from the database."""
    if not supabase_connected:
        return []
    
    try:
        response = supabase.table('watchlistdata').select('userid').eq('isin', isin).execute()
        if response.data:
            return [user['userid'] for user in response.data]
        else:
            logger.error(f"Error fetching users by ISIN: {response.error}")
            return []
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return []

def get_user_by_category(category):
    """Get users by category from the database."""
    if not supabase_connected:
        return []
    
    try:
        response = supabase.table('watchlistdata').select('userid').eq('category', category).execute()
        if response.data:
            return [user['userid'] for user in response.data]
        else:
            logger.error(f"Error fetching users by category: {response.error}")
            return []
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return []
    
def getUserEmail(userids):
    """Get user email by user ID from the database."""
    email_ids = []
    for userid in userids:
        try:
            response = supabase.table('UserData').select('emailID').eq('UserID', userid).execute()
            if response.data:
                email_ids.append(response.data[0]['emailID'])
            else:
                logger.error(f"Error fetching email for user ID {userid}: {response.error}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

def get_all_users(isin, category):
    """Get all users by ISIN and category."""
    isinUsers = get_users_by_isin(isin)
    categoryUsers = get_user_by_category(category)

    # Combine both lists and remove duplicates
    allUsers = list(set(isinUsers) | set(categoryUsers))
    
    return allUsers

def get_all_users_email(isin,category):
    isinUsers = get_users_by_isin(isin)
    categoryUsers = get_user_by_category(category)

    allUsers = list(set(isinUsers) | set(categoryUsers))
    email_ids = getUserEmail(allUsers)

    return email_ids


# A simple health check endpoint
@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Simple health check endpoint"""
    if request.method == 'OPTIONS':
        return _handle_options()
    
    response = {
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat(),
        "server": "Financial Backend API (Custom Auth)",
        "supabase_connected": supabase_connected,
        "debug_mode": DEBUG_MODE,
        "environment": {
            "supabase_url_set": bool(os.getenv('SUPABASE_URL2')),
            "supabase_key_set": bool(os.getenv('SUPABASE_KEY2')),
        }
    }
    return jsonify(response), 200

# Also add a health check at the API path
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def api_health_check():
    """API health check endpoint"""
    return health_check()

# Function to handle OPTIONS requests
def _handle_options():
    response = app.make_default_options_response()
    headers = response.headers
    
    # Set CORS headers
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    headers["Access-Control-Max-Age"] = "3600"  # Cache preflight response for 1 hour
    
    return response

# Handle OPTIONS requests for all routes
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return _handle_options()


@app.route('/api/socket/health', methods=['GET'])
def socket_health():
    """Check Socket.IO server health - simplified version"""
    try:
        return jsonify({
            'socket_server_running': True,
            'socketio_initialized': socketio is not None,
            'async_mode': getattr(socketio, 'async_mode', 'unknown'),
            'server_available': hasattr(socketio, 'server') and socketio.server is not None,
            'status': 'healthy'
        }), 200
        
    except Exception as e:
        logger.error(f"Socket health check error: {str(e)}")
        return jsonify({
            'socket_server_running': False,
            'error': str(e),
            'status': 'error'
        }), 500

# Routes
@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return _handle_options()
        
    data = request.get_json()
    
    # Check if required fields exist
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    logger.info(f"Registration attempt for email: {email}")
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
    
    try:
        # Check if email already exists
        check_response = supabase.table('UserData').select('emailID').eq('emailID', email).execute()
        
        if check_response.data and len(check_response.data) > 0:
            return jsonify({'message': 'Email already registered. Please use a different email or try logging in.'}), 409
        
        # Generate new UUID for user
        user_id = str(uuid.uuid4())
        
        # Generate access token
        access_token = generate_access_token()
        
        # Hash the password
        hashed_password = hash_password(password)
        
        # Generate a UUID for the watchlist
        watchlist_id = str(uuid.uuid4())
        
        # Create initial watchlist in watchlistnamedata
        supabase.table('watchlistnamedata').insert({
            'watchlistid': watchlist_id,
            'watchlistname': 'Real Time Alerts',
            'userid': user_id
        }).execute()
        
        # Store the generated watchlist ID
        watchlist = watchlist_id
        
        # Create user data
        user_data = {
            'UserID': user_id,
            'emailID': email,
            'Password': hashed_password,
            'Phone_Number': data.get('phone', None),
            'Paid': 'false',
            'AccountType': data.get('account_type', 'free'),
            'created_at': datetime.datetime.now().isoformat(),
            'AccessToken': access_token,
            'WatchListID': watchlist
        }
        
        # Insert user into UserData table
        supabase.table('UserData').insert(user_data).execute()
        
        logger.info(f"User registered successfully: {user_id}")
        
        # Return success with token
        return jsonify({
            'message': 'User registered successfully!',
            'user_id': user_id,
            'token': access_token
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return _handle_options()
        
    data = request.get_json()
    
    # Check if required fields exist
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    logger.info(f"Login attempt for email: {email}")
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
    
    try:
        # Find user by email
        response = supabase.table('UserData').select('*').eq('emailID', email).execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({'message': 'Invalid email or password.'}), 401
            
        user = response.data[0]
        
        # Verify password
        if not verify_password(user['Password'], password):
            return jsonify({'message': 'Invalid email or password.'}), 401
            
        # Generate new access token
        access_token = generate_access_token()
        
        # Update access token in database
        supabase.table('UserData').update({'AccessToken': access_token}).eq('UserID', user['UserID']).execute()
        
        logger.info(f"User logged in successfully: {user['UserID']}")
        
        # Return success with token
        return jsonify({
            'message': 'Login successful!',
            'user_id': user['UserID'],
            'token': access_token
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'message': f'Login failed: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST', 'OPTIONS'])
@auth_required
def logout(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()
    
    user_id = current_user['UserID']
    logger.info(f"Logout attempt for user: {user_id}")
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
        
    try:
        # Invalidate the token by setting it to null or empty
        supabase.table('UserData').update({'AccessToken': None}).eq('UserID', user_id).execute()
        
        logger.info(f"User logged out successfully: {user_id}")
        return jsonify({'message': 'Logged out successfully!'}), 200
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'message': f'Logout failed: {str(e)}'}), 500

@app.route('/api/user', methods=['GET', 'OPTIONS'])
@auth_required
def get_user(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()
    
    # The current_user is already loaded from the middleware
    user_id = current_user['UserID']
    logger.debug(f"Get user profile for user: {user_id}")
    
    # Remove sensitive information
    user_data = {k: v for k, v in current_user.items() if k.lower() not in ['password', 'accesstoken']}
    return jsonify(user_data), 200

@app.route('/api/update_user', methods=['PUT', 'OPTIONS'])
@auth_required
def update_user(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()
        
    data = request.get_json()
    user_id = current_user['UserID']
    logger.info(f"Update user profile for user: {user_id}")
    
    # Remove fields that shouldn't be updated directly
    safe_data = {k: v for k, v in data.items() if k.lower() not in ['userid', 'accesstoken', 'password', 'email', 'emailid']}
    
    # Handle password change separately if provided
    if 'new_password' in data and data.get('current_password'):
        # Verify current password
        if not verify_password(current_user['Password'], data.get('current_password')):
            return jsonify({'message': 'Current password is incorrect.'}), 401
            
        # Update with new hashed password
        safe_data['Password'] = hash_password(data.get('new_password'))
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
    
    try:
        # Update user data in UserData table
        supabase.table('UserData').update(safe_data).eq('UserID', user_id).execute()
        logger.debug(f"User data updated successfully: {user_id}")
        return jsonify({'message': 'User data updated successfully!'}), 200
    except Exception as e:
        logger.error(f"User update error: {str(e)}")
        return jsonify({'message': f'Update failed: {str(e)}'}), 500

@app.route('/api/upgrade_account', methods=['POST', 'OPTIONS'])
@auth_required
def upgrade_account(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()
        
    data = request.get_json()
    user_id = current_user['UserID']
    account_type = data.get('account_type', 'premium')
    logger.info(f"Upgrade account for user: {user_id} to {account_type}")
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
    
    try:
        # Update account type and payment status
        update_data = {
            'Paid': 'true',
            'AccountType': account_type,
            'PaidTime': datetime.datetime.now().isoformat()
        }
        
        supabase.table('UserData').update(update_data).eq('UserID', user_id).execute()
        logger.debug(f"Account upgraded successfully: {user_id}")
        return jsonify({'message': 'Account upgraded successfully!'}), 200
    except Exception as e:
        logger.error(f"Account upgrade error: {str(e)}")
        return jsonify({'message': f'Upgrade failed: {str(e)}'}), 500

# Watchlist APIs
#!/usr/bin/env python3
"""
Supabase API Response Fix

This script contains fixed versions of the watchlist API endpoint functions 
that properly handle the Supabase Python SDK responses.
"""

# Fixed Watchlist API Endpoints
@app.route('/api/watchlist', methods=['GET', 'OPTIONS'])
@auth_required
def get_watchlist(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()

    user_id = current_user['UserID']
    logger.debug(f"Get watchlist for user: {user_id}")

    try:
        # Step 1: Get all watchlists for the user
        response = supabase.table('watchlistnamedata') \
            .select('watchlistid, watchlistname') \
            .eq('userid', user_id).execute()

        # No need to check status_code - just check for error
        if hasattr(response, 'error') and response.error:
            logger.error(f"Error fetching watchlistnamedata: {response.error}")
            return jsonify({'message': 'Error fetching watchlists.'}), 500

        watchlist_meta = response.data

        # Step 2: For each watchlist, get ISINs and category separately
        watchlists = []
        for entry in watchlist_meta:
            watchlist_id = entry['watchlistid']
            watchlist_name = entry['watchlistname']

            # Get ISINs (where category is NULL)
            isin_response = supabase.table('watchlistdata') \
                .select('isin') \
                .eq('watchlistid', watchlist_id) \
                .eq('userid', user_id) \
                .is_('category', 'null') \
                .execute()

            # Get category (where isin is NULL)
            cat_response = supabase.table('watchlistdata') \
                .select('category') \
                .eq('watchlistid', watchlist_id) \
                .eq('userid', user_id) \
                .is_('isin', 'null') \
                .execute()

            isins = [row['isin'] for row in isin_response.data] if isin_response.data else []
            category = cat_response.data[0]['category'] if cat_response.data else None

            watchlists.append({
                '_id': watchlist_id,
                'watchlistName': watchlist_name,
                'category': category,
                'isin': isins
            })

        return jsonify({'watchlists': watchlists}), 200

    except Exception as e:
        logger.error(f"Get watchlist error: {str(e)}")
        return jsonify({'message': f'Failed to retrieve watchlist: {str(e)}'}), 500


@app.route('/api/watchlist', methods=['POST', 'OPTIONS'])
@auth_required
def create_watchlist(current_user):
    if request.method == 'OPTIONS':
        return _handle_options()

    data = request.get_json() or {}
    user_id = current_user['UserID']
    logger.info(f"Create/watchlist operation for user: {user_id}")

    try:
        operation = data.get('operation')

        if operation == 'create':
            # Create a new watchlist
            watchlist_id = str(uuid.uuid4())
            watchlist_name = data.get('watchlistName', 'My Watchlist')

            # Insert into watchlistnamedata
            insert_response = supabase.table('watchlistnamedata').insert({
                'watchlistid': watchlist_id,
                'watchlistname': watchlist_name,
                'userid': user_id
            }).execute()

            # Check for error instead of status_code
            if hasattr(insert_response, 'error') and insert_response.error:
                logger.error(f"Failed to create watchlist: {insert_response.error}")
                return jsonify({'message': 'Failed to create watchlist.'}), 500

            logger.debug(f"Watchlist {watchlist_id} created for user {user_id}")
            return jsonify({
                'message': 'Watchlist created!',
                'watchlist': {
                    '_id': watchlist_id,
                    'watchlistName': watchlist_name,
                    'category': None,
                    'isin': []
                }
            }), 201

        elif operation == 'add_isin':
            # Add ISIN to watchlistdata
            watchlist_id = data.get('watchlist_id')
            isin = data.get('isin')
            category = data.get('category')

            if not watchlist_id:
                return jsonify({'message': 'watchlist_id is required.'}), 400

            if isin is not None:
                if not isinstance(isin, str) or len(isin) != 12 or not isin.isalnum():
                    return jsonify({'message': 'Invalid ISIN format! ISIN must be a 12-character alphanumeric code.'}), 400

            # Check if ISIN already exists in this watchlist
            check = supabase.table('watchlistdata').select('isin') \
                .eq('watchlistid', watchlist_id) \
                .eq('userid', user_id) \
                .eq('isin', isin) \
                .execute()
                
            if check.data:
                return jsonify({'message': 'ISIN already exists in this watchlist!'}), 409

            # First, if category is provided, update or insert the category row
            if category:
                # Check if category row exists
                cat_check = supabase.table('watchlistdata').select('category') \
                    .eq('watchlistid', watchlist_id) \
                    .eq('userid', user_id) \
                    .is_('isin', 'null') \
                    .execute()
                    
                if cat_check.data:
                    # Update existing category
                    supabase.table('watchlistdata') \
                        .update({'category': category}) \
                        .eq('watchlistid', watchlist_id) \
                        .eq('userid', user_id) \
                        .is_('isin', 'null') \
                        .execute()
                else:
                    # Insert new category row
                    supabase.table('watchlistdata').insert({
                        'watchlistid': watchlist_id,
                        'userid': user_id,
                        'category': category,
                        'isin': None
                    }).execute()

            # Then insert ISIN row (with null category)
            insert = supabase.table('watchlistdata').insert({
                'watchlistid': watchlist_id,
                'userid': user_id,
                'isin': isin,
                'category': None
            }).execute()

            # Check for error instead of status_code
            if hasattr(insert, 'error') and insert.error:
                logger.error(f"Failed to add ISIN: {insert.error}")
                return jsonify({'message': 'Failed to add ISIN to watchlist.'}), 500

            logger.debug(f"ISIN {isin} added to watchlist {watchlist_id} for user {user_id}")
            return jsonify({
                'message': 'ISIN added to watchlist!',
                'watchlist_id': watchlist_id,
                'isin': isin,
                'category': category
            }), 201

        else:
            return jsonify({'message': 'Invalid operation! Use "create" or "add_isin".'}), 400

    except Exception as e:
        logger.error(f"Watchlist operation error: {str(e)}")
        return jsonify({'message': f'Failed to perform watchlist operation: {str(e)}'}), 500


@app.route('/api/watchlist/<watchlist_id>/isin/<isin>', methods=['DELETE', 'OPTIONS'])
@auth_required
def remove_from_watchlist(current_user, watchlist_id, isin):
    if request.method == 'OPTIONS':
        return _handle_options()

    user_id = current_user['UserID']
    logger.info(f"Remove ISIN {isin} from watchlist {watchlist_id} for user: {user_id}")

    try:
        # First verify the watchlist belongs to the user
        wl_check = supabase.table('watchlistnamedata').select('watchlistid') \
            .eq('watchlistid', watchlist_id).eq('userid', user_id).execute()
        
        if not wl_check.data:
            return jsonify({'message': 'Watchlist not found or unauthorized!'}), 404
        
        # Delete the specific ISIN from the watchlist
        delete_response = supabase.table('watchlistdata') \
            .delete() \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .eq('isin', isin) \
            .execute()
            
        # Check for error and empty data instead of status_code
        if (hasattr(delete_response, 'error') and delete_response.error) or not delete_response.data:
            return jsonify({'message': 'ISIN not found in watchlist!'}), 404
        
        # Get the updated watchlist data to return
        wl_name_response = supabase.table('watchlistnamedata') \
            .select('watchlistname') \
            .eq('watchlistid', watchlist_id).execute()
            
        # Get ISINs (where category is NULL)
        isin_response = supabase.table('watchlistdata') \
            .select('isin') \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .is_('category', 'null') \
            .execute()

        # Get category (where isin is NULL)
        cat_response = supabase.table('watchlistdata') \
            .select('category') \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .is_('isin', 'null') \
            .execute()
            
        watchlist_name = wl_name_response.data[0]['watchlistname'] if wl_name_response.data else "Unknown"
        isins = [row['isin'] for row in isin_response.data] if isin_response.data else []
        category = cat_response.data[0]['category'] if cat_response.data else None
        
        updated_watchlist = {
            '_id': watchlist_id,
            'watchlistName': watchlist_name,
            'category': category,
            'isin': isins
        }

        logger.debug(f"ISIN {isin} removed from watchlist for user: {user_id}")
        return jsonify({
            'message': 'ISIN removed from watchlist!',
            'watchlist': updated_watchlist
        }), 200
        
    except Exception as e:
        logger.error(f"Remove from watchlist error: {str(e)}")
        return jsonify({'message': f'Failed to remove ISIN from watchlist: {str(e)}'}), 500


@app.route('/api/watchlist/<watchlist_id>', methods=['DELETE', 'OPTIONS'])
@auth_required
def delete_watchlist(current_user, watchlist_id):
    if request.method == 'OPTIONS':
        return _handle_options()

    user_id = current_user['UserID']
    logger.info(f"Delete watchlist {watchlist_id} for user: {user_id}")

    try:
        # First verify the watchlist belongs to the user
        wl_check = supabase.table('watchlistnamedata').select('watchlistid') \
            .eq('watchlistid', watchlist_id).eq('userid', user_id).execute()
        
        if not wl_check.data:
            return jsonify({'message': 'Watchlist not found or unauthorized!'}), 404
        
        # The foreign key constraint with ON DELETE CASCADE will automatically delete 
        # related watchlistdata entries when the parent watchlistnamedata is deleted
        delete_response = supabase.table('watchlistnamedata') \
            .delete() \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .execute()
            
        # Check for error and empty data instead of status_code
        if (hasattr(delete_response, 'error') and delete_response.error) or not delete_response.data:
            return jsonify({'message': 'Failed to delete watchlist!'}), 500
            
        # Get the updated list of watchlists to return
        wl_response = supabase.table('watchlistnamedata') \
            .select('watchlistid, watchlistname') \
            .eq('userid', user_id).execute()
            
        watchlists = []
        for entry in wl_response.data:
            wl_id = entry['watchlistid']
            wl_name = entry['watchlistname']
            
            # Get ISINs (where category is NULL)
            isin_response = supabase.table('watchlistdata') \
                .select('isin') \
                .eq('watchlistid', wl_id) \
                .eq('userid', user_id) \
                .is_('category', 'null') \
                .execute()

            # Get category (where isin is NULL)
            cat_response = supabase.table('watchlistdata') \
                .select('category') \
                .eq('watchlistid', wl_id) \
                .eq('userid', user_id) \
                .is_('isin', 'null') \
                .execute()
                
            isins = [row['isin'] for row in isin_response.data] if isin_response.data else []
            category = cat_response.data[0]['category'] if cat_response.data else None
            
            watchlists.append({
                '_id': wl_id,
                'watchlistName': wl_name,
                'category': category,
                'isin': isins
            })
            

        logger.debug(f"Watchlist {watchlist_id} deleted for user: {user_id}")
        return jsonify({
            'message': 'Watchlist deleted successfully!',
            'watchlists': watchlists
        }), 200
        
    except Exception as e:
        logger.error(f"Delete watchlist error: {str(e)}")
        return jsonify({'message': f'Failed to delete watchlist: {str(e)}'}), 500


@app.route('/api/watchlist/<watchlist_id>/clear', methods=['POST', 'OPTIONS'])
@auth_required
def clear_watchlist(current_user, watchlist_id):
    if request.method == 'OPTIONS':
        return _handle_options()

    user_id = current_user['UserID']
    logger.info(f"Clear watchlist {watchlist_id} for user: {user_id}")

    try:
        # First verify the watchlist belongs to the user
        wl_check = supabase.table('watchlistnamedata').select('watchlistid, watchlistname') \
            .eq('watchlistid', watchlist_id).eq('userid', user_id).execute()
        
        if not wl_check.data:
            return jsonify({'message': 'Watchlist not found or unauthorized!'}), 404
            
        watchlist_name = wl_check.data[0]['watchlistname']
        
        # Delete only the ISIN entries (keep the category)
        clear_response = supabase.table('watchlistdata') \
            .delete() \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .not_.is_('isin', 'null') \
            .execute()
            
        # Check for error instead of status_code
        if hasattr(clear_response, 'error') and clear_response.error:
            return jsonify({'message': 'Failed to clear watchlist!'}), 500
            
        # Get all watchlists for return
        wl_response = supabase.table('watchlistnamedata') \
            .select('watchlistid, watchlistname') \
            .eq('userid', user_id).execute()
            
        watchlists = []
        for entry in wl_response.data:
            wl_id = entry['watchlistid']
            wl_name = entry['watchlistname']
            
            # Get ISINs (where category is NULL)
            isin_response = supabase.table('watchlistdata') \
                .select('isin') \
                .eq('watchlistid', wl_id) \
                .eq('userid', user_id) \
                .is_('category', 'null') \
                .execute()

            # Get category (where isin is NULL)
            cat_response = supabase.table('watchlistdata') \
                .select('category') \
                .eq('watchlistid', wl_id) \
                .eq('userid', user_id) \
                .is_('isin', 'null') \
                .execute()
                
            isins = [row['isin'] for row in isin_response.data] if isin_response.data else []
            category = cat_response.data[0]['category'] if cat_response.data else None
            
            watchlists.append({
                '_id': wl_id,
                'watchlistName': wl_name,
                'category': category,
                'isin': isins
            })
            
        # Find the cleared watchlist in the list
        cleared_watchlist = next((wl for wl in watchlists if wl['_id'] == watchlist_id), None)
        if not cleared_watchlist:
            cleared_watchlist = {
                '_id': watchlist_id,
                'watchlistName': watchlist_name,
                'category': None, 
                'isin': []
            }

        logger.debug(f"Watchlist {watchlist_id} cleared for user: {user_id}")
        return jsonify({
            'message': 'Watchlist cleared successfully!',
            'watchlist': cleared_watchlist,
            'watchlists': watchlists
        }), 200
        
    except Exception as e:
        logger.error(f"Clear watchlist error: {str(e)}")
        return jsonify({'message': f'Failed to clear watchlist: {str(e)}'}), 500
    
@app.route('/api/watchlist/bulk_add', methods=['POST', 'OPTIONS'])
@auth_required
def bulk_add_isins(current_user):
    """Add multiple ISINs to a watchlist in a single operation"""
    if request.method == 'OPTIONS':
        return _handle_options()

    data = request.get_json() or {}
    user_id = current_user['UserID']
    logger.info(f"Bulk add ISINs for user: {user_id}")

    try:
        # Required parameters
        watchlist_id = data.get('watchlist_id')
        isins = data.get('isins', [])
        category = data.get('category')  # Optional

        # Validate parameters
        if not watchlist_id:
            return jsonify({'message': 'watchlist_id is required'}), 400
            
        if not isinstance(isins, list):
            return jsonify({'message': 'isins must be an array'}), 400
            
        if len(isins) == 0:
            return jsonify({'message': 'isins array cannot be empty'}), 400
        
        # Verify the watchlist exists and belongs to the user
        wl_check = supabase.table('watchlistnamedata').select('watchlistid') \
            .eq('watchlistid', watchlist_id).eq('userid', user_id).execute()
            
        if not wl_check.data:
            return jsonify({'message': 'Watchlist not found or unauthorized'}), 404

        # Set category if provided
        if category:
            # Check if category row exists
            cat_check = supabase.table('watchlistdata').select('category') \
                .eq('watchlistid', watchlist_id) \
                .eq('userid', user_id) \
                .is_('isin', 'null') \
                .execute()
                
            if cat_check.data:
                # Update existing category
                supabase.table('watchlistdata') \
                    .update({'category': category}) \
                    .eq('watchlistid', watchlist_id) \
                    .eq('userid', user_id) \
                    .is_('isin', 'null') \
                    .execute()
            else:
                # Insert new category row
                supabase.table('watchlistdata').insert({
                    'watchlistid': watchlist_id,
                    'userid': user_id,
                    'category': category,
                    'isin': None
                }).execute()

        # Track results
        successful_isins = []
        failed_isins = []
        duplicate_isins = []
        
        # Process each ISIN individually
        for isin in isins:
            # Skip None or empty values
            if not isin:
                continue
                
            # Validate ISIN format
            if not isinstance(isin, str) or len(isin) != 12 or not isin.isalnum():
                failed_isins.append({
                    'isin': isin, 
                    'reason': 'Invalid ISIN format. ISIN must be a 12-character alphanumeric code.'
                })
                continue
                
            # Check if ISIN already exists in this watchlist
            check = supabase.table('watchlistdata').select('isin') \
                .eq('watchlistid', watchlist_id) \
                .eq('userid', user_id) \
                .eq('isin', isin) \
                .execute()
                
            if check.data:
                duplicate_isins.append(isin)
                continue
            
            # Insert ISIN row (with null category)
            try:
                insert = supabase.table('watchlistdata').insert({
                    'watchlistid': watchlist_id,
                    'userid': user_id,
                    'isin': isin,
                    'category': None
                }).execute()
                
                # Check for errors
                if hasattr(insert, 'error') and insert.error:
                    failed_isins.append({
                        'isin': isin, 
                        'reason': f"Database error: {insert.error}"
                    })
                else:
                    successful_isins.append(isin)
                    
            except Exception as e:
                failed_isins.append({
                    'isin': isin, 
                    'reason': str(e)
                })
        
        # Get updated watchlist data
        # Get ISINs (where category is NULL)
        isin_response = supabase.table('watchlistdata') \
            .select('isin') \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .is_('category', 'null') \
            .execute()

        # Get category (where isin is NULL)
        cat_response = supabase.table('watchlistdata') \
            .select('category') \
            .eq('watchlistid', watchlist_id) \
            .eq('userid', user_id) \
            .is_('isin', 'null') \
            .execute()
            
        # Get watchlist name
        name_response = supabase.table('watchlistnamedata') \
            .select('watchlistname') \
            .eq('watchlistid', watchlist_id) \
            .execute()
            
        watchlist_name = name_response.data[0]['watchlistname'] if name_response.data else "Unknown"
        isins = [row['isin'] for row in isin_response.data] if isin_response.data else []
        category_value = cat_response.data[0]['category'] if cat_response.data else None
        
        # Prepare watchlist object for response
        updated_watchlist = {
            '_id': watchlist_id,
            'watchlistName': watchlist_name,
            'category': category_value,
            'isin': isins
        }

        # Construct result message
        result_message = f"Added {len(successful_isins)} ISINs successfully"
        if duplicate_isins:
            result_message += f", {len(duplicate_isins)} duplicates skipped"
        if failed_isins:
            result_message += f", {len(failed_isins)} failed"

        logger.debug(f"Bulk add complete: {result_message}")
        return jsonify({
            'message': result_message,
            'successful': successful_isins,
            'duplicates': duplicate_isins,
            'failed': failed_isins,
            'watchlist': updated_watchlist
        }), 200

    except Exception as e:
        logger.error(f"Bulk add ISINs error: {str(e)}")
        return jsonify({'message': f'Failed to add ISINs: {str(e)}'}), 500
    
@app.route('/api/corporate_filings', methods=['GET', 'OPTIONS'])
def get_corporate_filings():
    """Endpoint to get corporate filings with improved date handling"""
    if request.method == 'OPTIONS':
        return _handle_options()
        
    try:
        # Get query parameters with proper error handling
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        category = request.args.get('category', '')
        symbol = request.args.get('symbol', '')
        isin = request.args.get('isin', '')
        
        logger.info(f"Corporate filings request: start_date={start_date}, end_date={end_date}, category={category}, symbol={symbol}, isin={isin}")
        
        if not supabase_connected:
            logger.error("Database service unavailable")
            return jsonify({'message': 'Database service unavailable. Please try again later.', 'status': 'error'}), 503
        
        # Build main query
        query = supabase.table('corporatefilings').select('*')
        
        # Order by date descending - most recent first
        query = query.order('date', desc=True)
        
        # Apply date filters if provided, using ISO format for correct string comparison
        if start_date:
            try:
                # Parse user input (YYYY-MM-DD)
                start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
                # Convert to ISO format with time at start of day (00:00:00)
                start_iso = start_dt.isoformat()
                logger.debug(f"Filtering dates >= {start_iso}")
                query = query.gte('date', start_iso)
            except ValueError as e:
                logger.error(f"Invalid start_date format: {start_date} - {str(e)}")
                return jsonify({'message': 'Invalid start_date format. Use YYYY-MM-DD', 'status': 'error'}), 400
        
        if end_date:
            try:
                # Parse user input (YYYY-MM-DD)
                end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
                # Set time to end of day (23:59:59)
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                # Convert to ISO format
                end_iso = end_dt.isoformat()
                logger.debug(f"Filtering dates <= {end_iso}")
                query = query.lte('date', end_iso)
            except ValueError as e:
                logger.error(f"Invalid end_date format: {end_date} - {str(e)}")
                return jsonify({'message': 'Invalid end_date format. Use YYYY-MM-DD', 'status': 'error'}), 400
        
        # Apply additional filters if provided
        if category:
            query = query.eq('category', category)
        if symbol:
            query = query.eq('symbol', symbol)
        if isin:
            query = query.eq('isin', isin)

        
        # Execute query with error handling
        try:
            logger.debug("Executing Supabase query")
            response = query.execute()
            
            # Log the full response for debugging
            logger.debug(f"Query response: {response}")
            
            # Return results
            result_count = len(response.data) if response.data else 0
            logger.info(f"Retrieved {result_count} corporate filings")
            
            # If no results, try to return without date filters as fallback
            if result_count == 0:
                logger.warning("No results found with date filters, trying without filters")
                try:
                    # Build a simpler query without date filters
                    simple_query = supabase.table('corporatefilings').select('*').limit(10)
                    if category:
                        simple_query = simple_query.eq('category', category)
                    if symbol:
                        simple_query = simple_query.eq('symbol', symbol)
                    if isin:
                        simple_query = simple_query.eq('isin', isin)
                    
                    simple_response = simple_query.execute()
                    if simple_response.data and len(simple_response.data) > 0:
                        logger.info(f"Retrieved {len(simple_response.data)} filings without date filters")
                        return jsonify({
                            'count': len(simple_response.data),
                            'filings': simple_response.data,
                            'note': 'Date filters were ignored to return results'
                        }), 200
                except Exception as e:
                    logger.error(f"Fallback query also failed: {str(e)}")
                
                # If we still have no results, try the test data
                test_filings = generate_test_filings()
                logger.info("Returning generated test filings as fallback")
                return jsonify({
                    'count': len(test_filings),
                    'filings': test_filings,
                    'note': 'Using test data as fallback'
                }), 200
            
            # Return the actual results
            return jsonify({
                'count': result_count,
                'filings': response.data
            }), 200
            
        except Exception as e:
            logger.error(f"Supabase query error: {str(e)}")
            # Return test data as fallback
            test_filings = generate_test_filings()
            logger.info("Returning generated test filings due to query error")
            return jsonify({
                'count': len(test_filings),
                'filings': test_filings,
                'note': 'Using test data due to database error'
            }), 200
    
    except Exception as e:
        # Log the full error details
        logger.error(f"Unexpected error in get_corporate_filings: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Always return test data in case of unhandled errors
        test_filings = generate_test_filings()
        return jsonify({
            'count': len(test_filings),
            'filings': test_filings,
            'note': 'Using test data due to server error'
        }), 200
    
@app.route('/api/corporate_filings', methods=['GET', 'OPTIONS'])
def get_corpFiling():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    corp_id = request.args.get('corpo_id', '')

    query = supabase.table('corporatefilings').select('*')

    if corp_id:
        query = query.eq('corp_id', corp_id)
    
    response = query.execute()
    if hasattr(response, 'error') and response.error:
        logger.error(f"Failed to retrieve corporate filings: {response.error}")
        return jsonify({'message': 'Failed to retrieve corporate filings!'}), 500
    if not response.data:
        logger.warning(f"No corporate filings found for corp_id: {corp_id}")
        return jsonify({'message': 'No corporate filings found!'}), 404
    filings = response.data
    return jsonify(filings), 200

# Helper function to generate test filings
def generate_test_filings():
    """Generate test filing data for when database is unavailable"""
    current_time = datetime.datetime.now()
    
    return [
        {
            "id": f"test-1-{current_time.timestamp()}",
            "Symbol": "TC1",
            "symbol": "TC1",
            "ISIN": "TEST1234567890",
            "isin": "TEST1234567890",
            "Category": "Financial Results",
            "category": "Financial Results",
            "summary": "Test Company 1 announces financial results for Q1 2025",
            "ai_summary": "**Category:** Financial Results\n**Headline:** Q1 2025 Results\n\nTest Company 1 announces financial results for Q1 2025 with a 15% increase in revenue.",
            "date": current_time.isoformat(),
            "companyname": "Test Company 1",
            "corp_id": f"test-corp-1-{current_time.timestamp()}"
        },
        {
            "id": f"test-2-{current_time.timestamp()}",
            "Symbol": "TC2", 
            "symbol": "TC2",
            "ISIN": "TEST2234567890",
            "isin": "TEST2234567890",
            "Category": "Dividend",
            "category": "Dividend",
            "summary": "Test Company 2 announces dividend for shareholders",
            "ai_summary": "**Category:** Dividend\n**Headline:** Dividend Announcement\n\nTest Company 2 announces a dividend of ₹5 per share for shareholders, payable on June 15, 2025.",
            "date": (current_time - datetime.timedelta(days=1)).isoformat(),
            "companyname": "Test Company 2",
            "corp_id": f"test-corp-2-{current_time.timestamp()}"
        },
        {
            "id": f"test-3-{current_time.timestamp()}",
            "Symbol": "TC3",
            "symbol": "TC3",
            "ISIN": "TEST3234567890",
            "isin": "TEST3234567890",
            "Category": "Mergers & Acquisitions",
            "category": "Mergers & Acquisitions",
            "summary": "Test Company 3 announces merger with another company",
            "ai_summary": "**Category:** Mergers & Acquisitions\n**Headline:** Company Merger\n\nTest Company 3 announces a strategic merger with XYZ Corp valued at $500 million, expected to close in Q3 2025.",
            "date": (current_time - datetime.timedelta(days=2)).isoformat(),
            "companyname": "Test Company 3",
            "corp_id": f"test-corp-3-{current_time.timestamp()}"
        }
    ]

# Improved test endpoint that always returns data
@app.route('/api/test_corporate_filings', methods=['GET', 'OPTIONS'])
def test_corporate_filings():
    """Reliable test endpoint for corporate filings"""
    if request.method == 'OPTIONS':
        return _handle_options()
    
    # Generate test filings that match your schema
    test_filings = generate_test_filings()
    
    # Apply any filters from the query parameters (optional)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    category = request.args.get('category', '')
    
    logger.info(f"Test corporate filings request with filters: start_date={start_date}, end_date={end_date}, category={category}")
    
    # Log that we're using test data
    logger.info(f"Returning {len(test_filings)} test filings")
    
    return jsonify({
        'count': len(test_filings),
        'filings': test_filings,
        'note': 'This is test data from the test endpoint'
    }), 200

@app.route('/api/stock_price', methods=['GET', 'OPTIONS'])
@auth_required
def get_stock_price():
    """Endpoint to get stock price data"""
    if request.method == 'OPTIONS':
        return _handle_options()
    
    # Example implementation for stock price retrieval
    isin = request.args.get('isin', '')
    if not isin:
        return jsonify({'message': 'Missing isin parameter!'}), 400
    
    response = supabase.table('stockpricedata').select('close','date').eq('isin', isin).order('date', desc=True).execute()
    if hasattr(response, 'error') and response.error:
        logger.error(f"Failed to retrieve stock price: {response.error}")
        return jsonify({'message': 'Failed to retrieve stock price!'}), 500
    if not response.data:
        logger.warning(f"No stock price data found for ISIN: {isin}")
        return jsonify({'message': 'No stock price data found!'}), 404
    stock_price = response.data

    return jsonify(stock_price), 200

# @# Add this to the top of your liveserver.py file, after the existing imports

# Advanced in-memory cache for deduplication
class AnnouncementCache:
    """Cache to prevent duplicate announcement processing"""
    def __init__(self, max_size=1000):
        self.cache = {}  # Main cache
        self.cache_by_content = {}  # Secondary cache using content hash
        self.max_size = max_size
        self.access_order = []  # For LRU eviction

    def _generate_content_hash(self, data):
        """Create a hash from announcement content for deduplication"""
        # Use multiple fields to generate a more robust hash
        hash_fields = []
        
        # Try different field combinations
        if 'companyname' in data and 'summary' in data:
            hash_fields.append(f"{data['companyname']}:{data['summary'][:100]}")
        
        if 'company' in data and 'summary' in data:
            hash_fields.append(f"{data['company']}:{data['summary'][:100]}")
            
        if 'Symbol' in data and 'summary' in data:
            hash_fields.append(f"{data['Symbol']}:{data['summary'][:100]}")
            
        if 'symbol' in data and 'summary' in data:
            hash_fields.append(f"{data['symbol']}:{data['summary'][:100]}")
        
        if 'ai_summary' in data:
            hash_fields.append(data['ai_summary'][:100])
            
        # Fallback if none of the above are present
        if not hash_fields:
            # Use whatever we can find as a hash source
            for key in ['headline', 'title', 'description', 'text']:
                if key in data and data[key]:
                    hash_fields.append(str(data[key])[:100])
                    break
            
            # Last resort
            if not hash_fields:
                return None
        
        # Create a hash from the combined fields
        hash_source = "||".join(hash_fields)
        return hashlib.md5(hash_source.encode()).hexdigest()

    def _update_access(self, key):
        """Update the access order for LRU eviction"""
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        # Evict oldest if cache exceeds max size
        while len(self.cache) > self.max_size:
            oldest_key = self.access_order.pop(0)
            content_hash = self.cache.get(oldest_key, {}).get('content_hash')
            if content_hash and content_hash in self.cache_by_content:
                del self.cache_by_content[content_hash]
            if oldest_key in self.cache:
                del self.cache[oldest_key]

    def contains(self, data):
        """Check if announcement is already in cache"""
        # Check by ID
        announcement_id = data.get('id') or data.get('corp_id')
        if announcement_id and announcement_id in self.cache:
            self._update_access(announcement_id)
            return True
            
        # Check by content hash
        content_hash = self._generate_content_hash(data)
        if content_hash and content_hash in self.cache_by_content:
            self._update_access(content_hash)
            return True
            
        return False

    def add(self, data):
        """Add announcement to cache"""
        announcement_id = data.get('id') or data.get('corp_id')
        if not announcement_id:
            # Generate an ID if none exists
            announcement_id = f"generated-{datetime.datetime.now().timestamp()}"
        
        # Generate content hash
        content_hash = self._generate_content_hash(data)
        
        # Store metadata
        timestamp = datetime.datetime.now().isoformat()
        
        # Store in primary cache
        self.cache[announcement_id] = {
            'timestamp': timestamp,
            'content_hash': content_hash
        }
        
        # Store in content hash cache if available
        if content_hash:
            self.cache_by_content[content_hash] = {
                'id': announcement_id,
                'timestamp': timestamp
            }
        
        self._update_access(announcement_id)
        
        return announcement_id

# Initialize the cache
announcement_cache = AnnouncementCache(max_size=5000)

# Then replace your insert_new_announcement function with this improved version:

@app.route('/api/save_announcement', methods=['POST', 'OPTIONS'])
def save_announcement():
    """Endpoint to save announcements to the database without WebSocket broadcast"""
    if request.method == 'OPTIONS':
        return _handle_options()
        
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Received empty announcement data")
            return jsonify({'message': 'Missing data!', 'status': 'error'}), 400
        
        # Add timestamp if not present
        if 'timestamp' not in data:
            data['timestamp'] = datetime.datetime.now().isoformat()
        
        # Add a unique ID if not present
        if 'id' not in data and 'corp_id' not in data:
            data['id'] = f"announcement-{datetime.datetime.now().timestamp()}"
            
        # Log the save operation
        logger.info(f"Saving announcement to database (no broadcast): {data.get('companyname', 'Unknown')}: {data.get('summary', '')[:100]}...")
        
        # Save to database if we have Supabase connection
        if supabase_connected:
            try:
                # Check if the announcement already exists
                search_id =data.get('corp_id')
                exists = False
                
                if search_id:
                    response = supabase.table('corporatefilings').select('corp_id').eq('corp_id', search_id).execute()
                    exists = response.data and len(response.data) > 0
                
                if not exists:
                    # Insert into database
                    supabase.table('corporatefilings').insert(data).execute()
                    logger.debug(f"Announcement saved to database with ID: {search_id}")
                else:
                    logger.debug(f"Announcement already exists in database, skipping insert: {search_id}")
                    
                return jsonify({
                    'message': 'Announcement saved to database successfully',
                    'status': 'success',
                    'is_new': False,
                    'exists': exists
                }), 200
                
            except Exception as e:
                logger.error(f"Database error saving announcement: {str(e)}")
                return jsonify({'message': f'Database error: {str(e)}', 'status': 'error'}), 500
        else:
            logger.warning("Supabase not connected, announcement not saved to database")
            return jsonify({'message': 'Database not connected', 'status': 'error'}), 503
            
    except Exception as e:
        # Log the full error trace for debugging
        logger.error(f"Error saving announcement: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'message': f'Error saving announcement: {str(e)}', 'status': 'error'}), 500

@app.route('/api/insert_new_announcement', methods=['POST', 'OPTIONS'])
def insert_new_announcement():
    if request.method == 'OPTIONS':
        return _handle_options()

    try:
        data = request.get_json()
        if not data:
            logger.warning("No JSON data received")
            return jsonify({'message': 'No JSON data received', 'status': 'error'}), 400

        logger.info(f"Received data: {data}")

        new_announcement = {
            "id": data.get('corp_id'),
            "securityid": data.get('securityid'),
            "summary": data.get('summary'),
            "fileurl": data.get('fileurl'),
            "date": data.get('date'),
            "ai_summary": data.get('ai_summary'),
            "category": data.get('category'),
            "isin": data.get('isin'),
            "companyname": data.get('companyname'),
            "symbol": data.get('symbol'),
        }

        logger.info(f"Broadcasting: {new_announcement}")
        socketio.emit('new_announcement', new_announcement)
        isin = data.get('isin')
        category = data.get('category')
        corp_id = data.get('corp_id')
        user_ids = get_all_users(isin, category)
        for user_id in user_ids:
            response = supabase.table('UserData').select('emailData').eq('UserID', user_id).single().execute()
            if response.data:
                email_data = response.data['emailData'] or []
                if corp_id not in email_data:
                    email_data.append(corp_id)

                    supabase.table("UserData").update({"emailData": email_data}).eq("UserID", user_id).execute()

                    print("corp_id added successfully.")
                else:
                    print("corp_id already present.")
            else:
                print("UserID not found.")

        
        return jsonify({'message': 'Test announcement sent successfully!', 'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'message': f'Error sending test announcement: {str(e)}', 'status': 'error'}), 500



# Testing endpoint to manually send a test announcement
@app.route('/api/test_announcement', methods=['POST', 'OPTIONS'])
def test_announcement():
    """Endpoint to manually send a test announcement for testing WebSocket"""
    if request.method == 'OPTIONS':
        return _handle_options()
        
    try:
        # Create test announcement data
        test_announcement = {
            'id': f"test-{datetime.datetime.now().timestamp()}",
            'companyname': 'Anshul',
            'symbol': 'ANSHUL',
            'category': 'ABC',
            'summary': 'Just Checking in',
            'ai_summary': '**Category:** Test Announcement\n**Headline:** Test WebSocket Functionality\n\nThis is a test announcement to verify WebSocket functionality.',
            'isin': 'TEST12345678',
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        # Broadcast to all clients
        socketio.emit('new_announcement', test_announcement)
        logger.info("Broadcasted test announcement to all clients")
        
        return jsonify({
            'message': 'Test announcement sent successfully!',
            'status': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"Error sending test announcement: {str(e)}")
        return jsonify({'message': f'Error sending test announcement: {str(e)}', 'status': 'error'}), 500

@app.route('/api/company/search', methods=['GET', 'OPTIONS'])
def search_companies():
    if request.method == 'OPTIONS':
        return _handle_options()
        
    try:
        # Get search parameters
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit')
        
        # Validate and convert limit to integer if provided
        if limit:
            try:
                limit = int(limit)
                if limit < 1:
                    return jsonify({'message': 'Limit must be a positive integer'}), 400
            except ValueError:
                return jsonify({'message': 'Limit must be a valid integer'}), 400
        
        # If no search query is provided, return an error
        if not query:
            return jsonify({'message': 'Search query is required (use parameter q)'}), 400
        
        logger.debug(f"Search companies: query={query}, limit={limit}")
        
        if not supabase_connected:
            return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
            
        # Initialize the Supabase query
        supabase_query = supabase.table('dhanstockdata').select('*')
        
        # Apply search filters (case-insensitive)
        search_pattern = f"%{query}%"
        
        # Build the query with proper OR conditions
        or_filter = (
            f"newname.ilike.{search_pattern},"
            f"oldname.ilike.{search_pattern},"
            f"newnsecode.ilike.{search_pattern},"
            f"oldnsecode.ilike.{search_pattern},"
            f"newbsecode.ilike.{search_pattern},"
            f"oldbsecode.ilike.{search_pattern},"
            f"isin.ilike.{search_pattern}"
        )
        filter_query = supabase_query.or_(or_filter)
        
        # Apply limit if provided
        if limit:
            filter_query = filter_query.limit(limit)
        
        # Execute the query
        response = filter_query.execute()
        
        # Check if response was successful
        if hasattr(response, 'error') and response.error is not None:
            return jsonify({'message': f'Error searching companies: {response.error.message}'}), 500
        
        # Return the search results
        return jsonify({
            'count': len(response.data),
            'companies': response.data
        }), 200
        
    except Exception as e:
        logger.error(f"Search companies error: {str(e)}")
        return jsonify({'message': f'Failed to search companies: {str(e)}'}), 500

# List all users (admin endpoint)
@app.route('/api/users', methods=['GET', 'OPTIONS'])
def list_users():
    if request.method == 'OPTIONS':
        return _handle_options()
    
    if not supabase_connected:
        return jsonify({'message': 'Database service unavailable. Please try again later.'}), 503
        
    try:
        # Get all users from the UserData table
        response = supabase.table('UserData').select('*').execute()
        
        # Remove sensitive information
        users = []
        for user in response.data:
            safe_user = {k: v for k, v in user.items() if k.lower() not in ['password', 'accesstoken']}
            users.append(safe_user)
            
        return jsonify({
            'count': len(users),
            'users': users
        }), 200
    except Exception as e:
        logger.error(f"List users error: {str(e)}")
        return jsonify({'message': f'Failed to list users: {str(e)}'}), 500

# Function to start the BSE scraper
# Function to start the BSE scraper
# Add this function to your liveserver.py file to fix the error

def start_scraper_bse():
    """Start the BSE scraper in a separate thread with better error handling"""
    try:
        logger.info("Starting BSE scraper in background thread...")
        
        # Get the path to the bse_scraper.py file
        scraper_path = Path(__file__).parent / "new_scraper.py"
        
        if not scraper_path.exists():
            logger.error(f"Scraper file not found at: {scraper_path}")
            return
            
        # Import the scraper module dynamically
        spec = importlib.util.spec_from_file_location("new_scraper", scraper_path)
        scraper_module = importlib.util.module_from_spec(spec)
        sys.modules["new_scraper"] = scraper_module
        spec.loader.exec_module(scraper_module)
        
        # Create and run the scraper
        today = datetime.datetime.today().strftime('%Y%m%d')
        
        try:
            # Create a flag file to signal that this is the first run
            first_run_flag_path = Path(__file__).parent / "data" / "first_run_flag.txt"
            os.makedirs(os.path.dirname(first_run_flag_path), exist_ok=True)
            
            # Mark as first run by creating the flag file
            with open(first_run_flag_path, 'w') as f:
                f.write(f"First run on {datetime.datetime.now().isoformat()}")
            
            logger.info("Created first run flag file")
                
            # Initialize the scraper
            scraper = scraper_module.BseScraper(today, today)
            
            # First run - this will use the flag file internally
            try:
                scraper.run()  # No parameter passed here
                logger.info("Initial scraper run completed")
            except Exception as e:
                logger.error(f"Error in initial scraper run: {str(e)}")
                logger.error(traceback.format_exc())
            
            # Remove the first run flag file
            if os.path.exists(first_run_flag_path):
                os.remove(first_run_flag_path)
                logger.info("Removed first run flag file")
            
            # Then poll periodically
            check_interval = 10  # seconds
            while True:
                try:
                    # Wait for next check interval
                    time.sleep(check_interval)
                    
                    # Update date to current date
                    current_day = datetime.datetime.today().strftime('%Y%m%d')
                    logger.debug(f"Running scheduled scraper check for date: {current_day}")
                    
                    # Create a new scraper instance each time to avoid state issues
                    scraper = scraper_module.BseScraper(current_day, current_day)
                    
                    # Run the scraper (after the first run)
                    scraper.run()
                    
                except Exception as e:
                    logger.error(f"Error in periodic scraper run: {str(e)}")
                    logger.error(traceback.format_exc())
                    # Continue the loop even after errors
            
        except Exception as e:
            logger.error(f"Error creating scraper instance: {str(e)}")
            logger.error(traceback.format_exc())
            
    except Exception as e:
        logger.error(f"Error importing scraper module: {str(e)}")
        logger.error(traceback.format_exc())

def start_scraper_nse():
    """Start the BSE scraper in a separate thread with better error handling"""
    try:
        logger.info("Starting BSE scraper in background thread...")
        
        # Get the path to the bse_scraper.py file
        scraper_path = Path(__file__).parent / "nse_scraper.py"
        
        if not scraper_path.exists():
            logger.error(f"Scraper file not found at: {scraper_path}")
            return
            
        # Import the scraper module dynamically
        spec = importlib.util.spec_from_file_location("nse_scraper", scraper_path)
        scraper_module = importlib.util.module_from_spec(spec)
        sys.modules["nse_scraper"] = scraper_module
        spec.loader.exec_module(scraper_module)
        
        # Create and run the scraper
        today = datetime.datetime.today().strftime('%d-%m-%Y')
        
        try:
            # Create a flag file to signal that this is the first run
            first_run_flag_path = Path(__file__).parent / "data" / "first_run_complete.txt"
            os.makedirs(os.path.dirname(first_run_flag_path), exist_ok=True)
            
            # Mark as first run by creating the flag file
            with open(first_run_flag_path, 'w') as f:
                f.write(f"First run on {datetime.datetime.now().isoformat()}")
            
            logger.info("Created first run flag file")
                
            # Initialize the scraper
            scraper = scraper_module.NseScraper(today, today)
            
            # First run - this will use the flag file internally
            try:
                scraper.run()  # No parameter passed here
                logger.info("Initial scraper run completed")
            except Exception as e:
                logger.error(f"Error in initial scraper run: {str(e)}")
                logger.error(traceback.format_exc())
            
            # Remove the first run flag file
            if os.path.exists(first_run_flag_path):
                os.remove(first_run_flag_path)
                logger.info("Removed first run flag file")
            
            # Then poll periodically
            check_interval = 10  # seconds
            while True:
                try:
                    # Wait for next check interval
                    time.sleep(check_interval)
                    
                    # Update date to current date
                    current_day = datetime.datetime.today().strftime('%d-%m-%Y')
                    logger.debug(f"Running scheduled scraper check for date: {current_day}")
                    
                    # Create a new scraper instance each time to avoid state issues
                    scraper = scraper_module.NseScraper(current_day, current_day)
                    
                    # Run the scraper (after the first run)
                    scraper.run()
                    
                except Exception as e:
                    logger.error(f"Error in periodic scraper run: {str(e)}")
                    logger.error(traceback.format_exc())
                    # Continue the loop even after errors
            
        except Exception as e:
            logger.error(f"Error creating scraper instance: {str(e)}")
            logger.error(traceback.format_exc())
            
    except Exception as e:
        logger.error(f"Error importing scraper module: {str(e)}")
        logger.error(traceback.format_exc())

# Global thread references to prevent garbage collection
scraper_threads = []
threads_started = False

def start_scrapers_safely():
    """Start scrapers with proper error handling and thread management"""
    global scraper_threads, threads_started
    
    if threads_started:
        logger.info("Scrapers already started, skipping initialization")
        return
    
    logger.info("Initializing scraper threads...")
    
    try:
        # Create threads with proper names
        bse_thread = threading.Thread(
            target=start_scraper_bse, 
            name="BSE-Scraper",
            daemon=False  # Important: not daemon
        )
        
        nse_thread = threading.Thread(
            target=start_scraper_nse, 
            name="NSE-Scraper", 
            daemon=False  # Important: not daemon
        )
        
        # Start threads
        bse_thread.start()
        nse_thread.start()
        
        # Store references
        scraper_threads.extend([bse_thread, nse_thread])
        threads_started = True
        
        logger.info(f"Started {len(scraper_threads)} scraper threads successfully")
        
        # Log thread status
        for thread in scraper_threads:
            logger.info(f"Thread {thread.name}: alive={thread.is_alive()}")
            
    except Exception as e:
        logger.error(f"Failed to start scraper threads: {str(e)}")
        logger.error(traceback.format_exc())

# Add thread monitoring endpoint
@app.route('/api/scraper_status', methods=['GET', 'OPTIONS'])
def scraper_status():
    """Check scraper thread status"""
    if request.method == 'OPTIONS':
        return _handle_options()
    
    global scraper_threads, threads_started
    
    status = {
        'threads_started': threads_started,
        'thread_count': len(scraper_threads),
        'threads': []
    }
    
    for thread in scraper_threads:
        status['threads'].append({
            'name': thread.name,
            'alive': thread.is_alive(),
            'daemon': thread.daemon
        })
    
    # Also show all active threads
    all_threads = threading.enumerate()
    status['all_threads'] = [
        {
            'name': t.name,
            'alive': t.is_alive(),
            'daemon': t.daemon
        } for t in all_threads
    ]
    
    return jsonify(status), 200

# Custom error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Endpoint not found!'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'message': 'Method not allowed!'}), 405

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'message': 'Internal server error!'}), 500

if __name__ == '__main__':
    # Print environment status
    logger.info(f"Starting Financial Backend API (Custom Auth) on port {PORT}")
    logger.info(f"Debug Mode: {'ENABLED' if DEBUG_MODE else 'DISABLED'}")
    logger.info(f"Supabase Connection: {'Successful' if supabase_connected else 'FAILED'}")
    
    # Start scrapers
    start_scrapers_safely()
    
    # Small delay to let threads initialize
    time.sleep(2)
    
    # Run with Socket.IO
    socketio.run(app, debug=DEBUG_MODE, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)

# Also start scrapers when module is imported (for Gunicorn)
else:
    # This runs when imported by Gunicorn
    logger.info("Module imported by WSGI server, initializing scrapers...")
    start_scrapers_safely()