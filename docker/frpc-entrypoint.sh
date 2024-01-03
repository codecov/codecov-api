#!/bin/sh
if [ $SERVER_ADDR ]; then
  sed -i "s|server_addr = 127.0.0.1|server_addr = $SERVER_ADDR|g" /frp/frpc.ini
fi
if [ $FRP_USER ]; then
  sed -i "1 a user = $FRP_USER" /frp/frpc.ini
fi
if [ $PROXY_NAME ]; then
  sed -i "s|ssh|$PROXY_NAME|g" /frp/frpc.ini
fi
if [ $SERVER_PORT ]; then
  sed -i "s|server_port = 7000|server_port = $SERVER_PORT|g" /frp/frpc.ini
fi
if [ $PROTO ]; then
  sed -i "s|type = tcp|type = $PROTO|g" /frp/frpc.ini
fi
if [ $LOCAL_IP ]; then
  sed -i "s|local_ip = 127.0.0.1|local_ip = $LOCAL_IP|g" /frp/frpc.ini
fi
if [ $LOCAL_PORT ]; then
  sed -i "s|local_port = 22|local_port = $LOCAL_PORT|g" /frp/frpc.ini
fi
if [ $REMOTE_PORT ]; then
  sed -i "s|remote_port = 6000|remote_port = $REMOTE_PORT|g" /frp/frpc.ini
fi
if [ $DOMAIN ]; then
  sed -i "s|subdomain = api|subdomain = $DOMAIN|g" /frp/frpc.ini
  sed -i "s|\[api\]|\[$DOMAIN\]|g" /frp/frpc.ini
fi
/frp/frpc -c /frp/frpc.ini