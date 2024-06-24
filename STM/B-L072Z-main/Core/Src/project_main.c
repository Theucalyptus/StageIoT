/* ==========================================================
 * project_main.c - 
 * Project : Disk91 SDK
 * ----------------------------------------------------------
 * Created on: 6 sept. 2018
 *     Author: Paul Pinault aka Disk91
 * ----------------------------------------------------------
 * Copyright (C) 2018 Disk91
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU LESSER General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Lesser Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 * ----------------------------------------------------------
 * 
 * Add a such file in the main Src directory for executing
 * you own workload.
 *
 * ==========================================================
 */
#include <it_sdk/config.h>
#include <it_sdk/itsdk.h>
#include <it_sdk/time/time.h>
#include <it_sdk/logger/logger.h>
#include <it_sdk/sched/scheduler.h>
#include <it_sdk/statemachine/statemachine.h>
#include <it_sdk/eeprom/eeprom.h>
#include <it_sdk/eeprom/sdk_config.h>

#include <it_sdk/lorawan/lorawan.h>
#include <it_sdk/encrypt/encrypt.h>
#include <it_sdk/eeprom/securestore.h>
#include <it_sdk/lowpower/lowpower.h>
#include <drivers/sx1276/sx1276.h>


#define COMFREQS	(1*5*1000)
#define TASKDELAYMS	(1000)

struct state {
	uint8_t 		led;
	uint32_t  		loops;
	int32_t			lastComMS;
	itsdk_bool_e	setup;
} s_state;


#define LED1_PORT 	__BANK_B
#define LED1_PIN 	__LP_GPIO_5
#define LED2_PORT 	__BANK_A
#define LED2_PIN 	__LP_GPIO_5
#define LED3_PORT 	__BANK_B
#define LED3_PIN 	__LP_GPIO_6
#define LED4_PORT 	__BANK_B
#define LED4_PIN 	__LP_GPIO_7
#define BUTTON_PORT	__BANK_B
#define BUTTON_PIN 	__LP_GPIO_2


uint8_t tx_buff[10] = "clement !\n";
uint8_t rx_buff[10];

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	log_info("======recu======");
	HAL_UART_Receive_IT(&huart1, rx_buff, 10); //You need to toggle a breakpoint on this line!
}

void task() {

	// Just to get something provinf the activity
	uint8_t t[4] = { '/','|','\\','-'};


	  if(HAL_UART_Receive(&huart1, rx_buff, 10, 1000)==HAL_OK) //if transfer is successful
	  {
	    HAL_UART_Transmit(&huart1, rx_buff, 10, 1000); //send back the received data
		log_info("======recu2======");
	  } else {
	    __NOP();
	  }

	//test d'envoi sur l'uart1
	HAL_UART_Transmit(&huart1, tx_buff, 10, 1000);

	log_info("\r%c ",t[s_state.loops & 3]);
	s_state.led = (s_state.led==__GPIO_VAL_SET)?__GPIO_VAL_RESET:__GPIO_VAL_SET;
	gpio_change(LED1_PORT, LED1_PIN,s_state.led);
	s_state.loops++;

	// wait for the board configuration
	uint8_t i = 0;
	uint8_t devEui[8] = {0};
	itsdk_lorawan_getDeviceEUI(devEui);

	while ( i < 8 && devEui[i] == 0 ) i++;
	if  ( i < 8 ) {
		if ( s_state.setup == BOOL_FALSE) {
			log_info("Init LoRawan Stack ");
			itsdk_lorawan_init_t r;
			#ifdef ITSDK_LORAWAN_CHANNEL
				static itsdk_lorawan_channelInit_t channels= ITSDK_LORAWAN_CHANNEL;
				r = itsdk_lorawan_setup(itsdk_config.sdk.activeRegion,&channels);
			#else
				r = itsdk_lorawan_setup(itsdk_config.sdk.activeRegion,NULL);
			#endif
			if ( r == LORAWAN_INIT_SUCESS ) {
				log_info("success\r\n");
				s_state.setup = BOOL_TRUE;
			} else {
				log_info("failed\r\n");
			}
		}
		if ( s_state.setup == BOOL_TRUE && s_state.lastComMS > COMFREQS) {
			// Send a LoRaWan Frame
			uint8_t * data[100];
			*data = "{\"timestamp\": \"2023-04-01T12:00:00Z\",\"luminosite\": 750,\"pression\": 1013.25,\"temperature\": 22.5}";
			if ( !itsdk_lorawan_hasjoined() ) {
				log_info("Connecting LoRaWAN ");
				if ( itsdk_lorawan_join_sync() == LORAWAN_JOIN_SUCCESS ) {
					gpio_set(LED4_PORT,LED4_PIN);
					log_info("success\r\n");
				} else {
					gpio_reset(LED4_PORT,LED4_PIN);
					log_info("failed\r\n");
					s_state.lastComMS = COMFREQS - 30*1000; // retry in 30 seconds
				}
			} else {
				log_info("Fire a LoRaWAN message ");
				uint8_t port;
				uint8_t size=100;
				uint8_t rx[100];
				itsdk_lorawan_send_t r = itsdk_lorawan_send_sync(
						data,						// Payload
						100,						// Payload size
						1,						// Port
						__LORAWAN_DR_5,			// Speed
						LORAWAN_SEND_CONFIRMED,	// With a ack
						ITSDK_LORAWAN_CNF_RETRY,// And default retry
						&port,					// In case of reception - Port (uint8_t)
						&size,					// In case of reception - Size (uint8_t) - init with buffer max size
						rx,						// In case of recpetion - Data (uint8_t[] bcopied)
						PAYLOAD_ENCRYPT_NONE	// End to End encryption mode
				);
				if ( r == LORAWAN_SEND_SENT || r == LORAWAN_SEND_ACKED ) {
					log_info("success\r\n",r);
				} else {
					log_info("failed (%d)\r\n",r);
				}
				s_state.lastComMS = 0;
			}
		} else {
			s_state.lastComMS += TASKDELAYMS;
		}
	}

}


// =====================================================================
// Setup
void project_setup() {
	log_info("Starting up\r\n");				// print a message on the USART2
	itsdk_delayMs(2000);
	log_info("Booting \r\n");

	//itsdk_config_resetToFactory();

	s_state.led = __GPIO_VAL_RESET;
	s_state.loops = 0;
	s_state.lastComMS = COMFREQS;
	s_state.setup = BOOL_FALSE;
	gpio_change(LED1_PORT, LED1_PIN,s_state.led);
	gpio_reset(LED4_PORT,LED4_PIN);

	HAL_UART_Receive_IT(&huart1, rx_buff, 10);
	itdt_sched_registerSched(TASKDELAYMS,ITSDK_SCHED_CONF_IMMEDIATE, &task);

	static itsdk_lorawan_channelInit_t channels= ITSDK_LORAWAN_CHANNEL;
	#ifdef ITSDK_LORAWAN_CHANNEL
		itsdk_lorawan_setup(__LORAWAN_REGION_EU868,&channels);
	#else
		itsdk_lorawan_setup(__LORAWAN_REGION_EU868,NULL);
	#endif

	log_info("LoRa boot \r\n");
	while ( itsdk_lorawan_hasjoined() ) {
		log_info("trying to connect \r\n");
		itsdk_lorawan_join_sync();
	}

	log_info("Connected \r\n");

	uint8_t frBuffer[10] = { 0,1,2,3,4,5,6,7,8,9 };
	uint8_t rPort;
	uint8_t rSize;
	uint8_t rData[16];
	itsdk_lorawan_send_sync(
				frBuffer,			// payload buffer
				10,					// payload size
				1,					// Port
				__LORAWAN_DR_5,		// speed
				LORAWAN_SEND_UNCONFIRMED,
				1,					// retry (not applicable for unconfirmed communications)
				&rPort,				// downlink port
				&rSize,				// downlink size
				rData,				// downlink data
				/*PAYLOAD_ENCRYPT_AESCTR | PAYLOAD_ENCRYPT_SPECK |*/ PAYLOAD_ENCRYPT_NONE
	);

}


/**
 * Project loop may not contain functional stuff
 * Keep in this loop only really short operations
 */
void project_loop() {
    itsdk_lorawan_loop();
}

